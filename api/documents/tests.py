"""Pruebas de los serializers de documentos."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from .models import Company, Document, EntityReference, ValidationFlow
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
            "bucket_key": "docs/contrato.pdf",
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
        self.assertTrue(
            ValidationFlow.objects.filter(document=document).exists(),
            "El flujo de validación no fue creado",
        )
        flow = document.validation_flow
        self.assertEqual(flow.steps.count(), 2)
        orders = list(flow.steps.values_list("order", flat=True))
        self.assertListEqual(orders, [1, 2])

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
            "bucket_key",
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