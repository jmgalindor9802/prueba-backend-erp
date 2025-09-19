"""Pruebas de los serializers de documentos."""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from unittest.mock import patch
from .models import (
    Company,
    CompanyMembership,
    Document,
    EntityReference,
    PendingDocumentUpload,
    ValidationFlow,
    ValidationStep,
    ValidationStatus,
)
from .serializers import (
    DocumentSerializer,
    ValidationFlowSerializer,
)


class DocumentSerializerTests(TestCase):
    """Casos de prueba para el serializer de documentos."""

    def setUp(self) -> None:
        self.company = Company.objects.create(name="Mi Empresa")
        self.entity = EntityReference.objects.create(
            entity_type="Cliente", external_identifier="C-123"
        )
        self.user = get_user_model().objects.create_user(
            username="approver", email="approver@example.com", password="pass1234"
        )

    def _base_payload(self) -> dict:
        return {
            "name": "Contrato",
            "mime_type": "application/pdf",
            "size": 2048,
            "company": str(self.company.id),
            "entity_reference": str(self.entity.id),
        }

    def test_crea_documento_con_flujo_de_validacion(self) -> None:
        """El serializer debe crear el documento y su flujo con pasos."""

        extra_user = get_user_model().objects.create_user(
            username="approver2", email="ap2@example.com", password="pass1234"
        )
        payload = self._base_payload()
        payload["validation_flow"] = {
            "steps": [
                {"order": 1, "approver": str(self.user.id)},
                {"order": 2, "approver": str(extra_user.id)},
            ]
        }

        serializer = DocumentSerializer(data=payload)
        self.assertTrue(serializer.is_valid(), serializer.errors)

        document = serializer.save(created_by=self.user)

        self.assertIsInstance(document, Document)
        self.assertEqual(document.created_by, self.user)
        self.assertEqual(document.bucket_name, settings.GS_BUCKET_NAME)
        self.assertTrue(document.bucket_key)
        self.assertEqual(document.validation_status, ValidationStatus.PENDING)
        self.assertTrue(
            ValidationFlow.objects.filter(document=document).exists(),
            "El flujo de validación no fue creado",
        )
        flow = document.validation_flow
        self.assertEqual(flow.steps.count(), 2)
        steps = list(flow.steps.order_by("order"))
        self.assertListEqual([step.order for step in steps], [1, 2])
        self.assertEqual([step.approver for step in steps], [self.user, extra_user])
        self.assertTrue(
            all(step.status == ValidationStatus.PENDING for step in steps),
            "Los pasos deben iniciar en estado pendiente",
        )

    def test_rechaza_tamano_superior_al_limite(self) -> None:
        """Cuando el tamaño excede el máximo se debe reportar un error."""

        payload = self._base_payload()
        payload["size"] = 25 * 1024 * 1024  # 25 MB

        with override_settings(DOCUMENTS_MAX_FILE_SIZE=10 * 1024 * 1024):
            serializer = DocumentSerializer(data=payload)
            self.assertFalse(serializer.is_valid())
            self.assertIn("size", serializer.errors)

    def test_rechaza_mime_type_no_permitido(self) -> None:
        """El serializer solo acepta tipos MIME permitidos."""

        payload = self._base_payload()
        payload["mime_type"] = "application/zip"

        serializer = DocumentSerializer(data=payload)
        self.assertFalse(serializer.is_valid())
        self.assertIn("mime_type", serializer.errors)

    def test_campos_obligatorios(self) -> None:
        """Se validan los campos requeridos del serializer."""

        serializer = DocumentSerializer(data={})
        self.assertFalse(serializer.is_valid())
        for field in [
            "name",
            "mime_type",
            "size",
            "company",
            "entity_reference",
        ]:
            self.assertIn(field, serializer.errors)

    def test_rechaza_ordenes_duplicadas_en_flujo(self) -> None:
        """Los pasos del flujo deben tener un orden único."""

        payload = self._base_payload()
        payload["validation_flow"] = {
            "steps": [
                {"order": 1, "approver": str(self.user.id)},
                {"order": 1, "approver": str(self.user.id)},
            ]
        }

        serializer = DocumentSerializer(data=payload)
        self.assertFalse(serializer.is_valid())
        self.assertIn("validation_flow", serializer.errors)


class ValidationFlowSerializerTests(TestCase):
    """Pruebas específicas del serializer de flujos de validación."""

    def setUp(self) -> None:
        self.company = Company.objects.create(name="Acme")
        self.entity = EntityReference.objects.create(
            entity_type="Proveedor", external_identifier="P-99"
        )
        self.document = Document.objects.create(
            name="Factura",
            mime_type="application/pdf",
            size=1024,
            bucket_name=settings.GS_BUCKET_NAME,
            bucket_key="docs/factura.pdf",
            company=self.company,
            entity_reference=self.entity,
        )

    def test_requiere_al_menos_un_paso(self) -> None:
        """No se puede crear un flujo sin pasos."""

        serializer = ValidationFlowSerializer(data={"steps": []})
        self.assertFalse(serializer.is_valid())
        self.assertIn("steps", serializer.errors)

    def test_crea_flujo_y_pasos(self) -> None:
        """Al guardar debe persistir el flujo y sus pasos."""

        payload = {"steps": [{"order": 1}, {"order": 2}]}
        serializer = ValidationFlowSerializer(data=payload)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        flow = serializer.save(document=self.document)

        self.assertIsNotNone(flow.pk)
        self.assertEqual(flow.document, self.document)
        self.assertEqual(flow.steps.count(), 2)
        self.assertListEqual(
            list(flow.steps.values_list("order", flat=True)),
            [1, 2],
        )


class DocumentViewSetTests(APITestCase):
    """Pruebas de integración para los endpoints del viewset de documentos."""

    def setUp(self) -> None:
        self.user = get_user_model().objects.create_user(
            username="member", email="member@example.com", password="pass1234"
        )
        self.other_user = get_user_model().objects.create_user(
            username="other", email="other@example.com", password="pass1234"
        )

        self.company = Company.objects.create(name="Acme Corp")
        CompanyMembership.objects.create(company=self.company, user=self.user)
        CompanyMembership.objects.create(company=self.company, user=self.other_user)

        self.entity = EntityReference.objects.create(
            entity_type="Cliente", external_identifier="CL-001"
        )

        self.client.force_authenticate(self.user)

    def _create_document_with_flow(self, assignments=None) -> Document:
        document = Document.objects.create(
            name="Contrato",
            mime_type="application/pdf",
            size=1024,
            bucket_name=settings.GS_BUCKET_NAME,
            bucket_key="docs/contrato.pdf",
            company=self.company,
            entity_reference=self.entity,
            created_by=self.user,
            validation_status=ValidationStatus.PENDING,
        )
        flow = ValidationFlow.objects.create(document=document)
        assignments = assignments or [
            (1, self.user),
            (2, self.other_user),
        ]
        for order, approver in assignments:
            ValidationStep.objects.create(
                flow=flow,
                order=order,
                approver=approver,
                status=ValidationStatus.PENDING,
            )
        return document

    def test_create_document_returns_pending_upload(self) -> None:
        url = reverse("document-list")
        payload = {
            "name": "Factura",
            "mime_type": "application/pdf",
            "size": 2048,
            "company": str(self.company.id),
            "entity_reference": str(self.entity.id),
        }

        with patch(
            "documents.views.generate_upload_signed_url",
            return_value="https://signed-upload",
        ) as mocked_upload:
            response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["upload_url"], "https://signed-upload")
        self.assertIn("upload_token", response.data)
        self.assertIn("bucket_key", response.data)
        self.assertIn("bucket_name", response.data)

        mocked_upload.assert_called_once()
        called_kwargs = mocked_upload.call_args.kwargs
        self.assertEqual(called_kwargs["bucket_name"], settings.GS_BUCKET_NAME)
        self.assertEqual(called_kwargs["mime_type"], "application/pdf")

        self.assertEqual(Document.objects.count(), 0)
        pending = PendingDocumentUpload.objects.get(
            id=response.data["upload_token"]
        )
        self.assertEqual(pending.company, self.company)
        self.assertEqual(pending.created_by, self.user)
        self.assertEqual(pending.bucket_key, called_kwargs["bucket_key"])

    def test_complete_upload_creates_document(self) -> None:
        url = reverse("document-list")
        payload = {
            "name": "Factura",
            "mime_type": "application/pdf",
            "size": 2048,
            "company": str(self.company.id),
            "entity_reference": str(self.entity.id),
            "validation_flow": {
                "steps": [{"order": 1, "approver": str(self.user.id)}]
            },
        }

        with patch(
            "documents.views.generate_upload_signed_url",
            return_value="https://signed-upload",
        ):
            create_response = self.client.post(url, payload, format="json")

        token = create_response.data["upload_token"]

        with patch("documents.views.blob_exists", return_value=True):
            response = self.client.post(
                reverse("document-complete-upload"),
                {"upload_token": token},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertFalse(PendingDocumentUpload.objects.filter(id=token).exists())
        document = Document.objects.get()
        self.assertEqual(document.created_by, self.user)
        self.assertEqual(document.bucket_name, settings.GS_BUCKET_NAME)
        self.assertEqual(document.validation_status, ValidationStatus.PENDING)
        self.assertEqual(document.validation_flow.steps.count(), 1)
        self.assertEqual(response.data["id"], str(document.id))

    def test_complete_upload_requires_existing_blob(self) -> None:
        payload = {
            "name": "Factura",
            "mime_type": "application/pdf",
            "size": 2048,
            "company": str(self.company.id),
            "entity_reference": str(self.entity.id),
        }

        with patch(
            "documents.views.generate_upload_signed_url",
            return_value="https://signed-upload",
        ):
            create_response = self.client.post(
                reverse("document-list"), payload, format="json"
            )

        token = create_response.data["upload_token"]

        with patch("documents.views.blob_exists", return_value=False):
            response = self.client.post(
                reverse("document-complete-upload"),
                {"upload_token": token},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Document.objects.count(), 0)
        self.assertTrue(PendingDocumentUpload.objects.filter(id=token).exists())

    def test_complete_upload_rejects_different_user(self) -> None:
        payload = {
            "name": "Factura",
            "mime_type": "application/pdf",
            "size": 2048,
            "company": str(self.company.id),
            "entity_reference": str(self.entity.id),
        }

        with patch(
            "documents.views.generate_upload_signed_url",
            return_value="https://signed-upload",
        ):
            create_response = self.client.post(
                reverse("document-list"), payload, format="json"
            )

        token = create_response.data["upload_token"]

        self.client.force_authenticate(self.other_user)

        with patch("documents.views.blob_exists", return_value=True):
            response = self.client.post(
                reverse("document-complete-upload"),
                {"upload_token": token},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Document.objects.count(), 0)
        self.assertTrue(PendingDocumentUpload.objects.filter(id=token).exists())

    def test_download_returns_signed_url(self) -> None:
        document = self._create_document_with_flow()
        url = reverse("document-download", kwargs={"pk": document.pk})

        with patch(
            "documents.views.generate_download_signed_url",
            return_value="https://signed-download",
        ) as mocked_download:
            response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["download_url"], "https://signed-download")
        mocked_download.assert_called_once()
        download_kwargs = mocked_download.call_args.kwargs
        self.assertEqual(download_kwargs["bucket_key"], document.bucket_key)
        self.assertEqual(download_kwargs["bucket_name"], document.bucket_name)

    def test_approve_updates_document_and_previous_steps(self) -> None:
        document = self._create_document_with_flow()

        url = reverse("document-approve", kwargs={"pk": document.pk})

        response = self.client.post(
            url,
            {"actor_user_id": str(self.user.id), "reason": "Todo correcto"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

        document.refresh_from_db()
        self.assertEqual(document.validation_status, ValidationStatus.APPROVED)
