"""Vistas para gestionar documentos y sus flujos de validación."""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError

from .models import Document, ValidationStatus
from .permissions import IsCompanyMember, IsStepApprover
from .serializers import DocumentSerializer
from .services import (
    build_document_bucket_key,
    default_bucket_name,
    generate_download_signed_url,
    generate_upload_signed_url,
)


class DocumentViewSet(mixins.CreateModelMixin, viewsets.GenericViewSet):
    """Endpoint principal para crear documentos y operar sobre su flujo."""

    serializer_class = DocumentSerializer
    permission_classes = [IsAuthenticated, IsCompanyMember]

    def get_permissions(self):
        permissions = super().get_permissions()
        if getattr(self, "action", None) in {"approve", "reject"}:
            permissions.append(IsStepApprover())
        return permissions

    def get_queryset(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            return Document.objects.none()

        return Document.objects.filter(
            company__memberships__user=user
        ).select_related(
            "company",
            "entity_reference",
            "created_by",
            "validation_flow",
        ).prefetch_related("validation_flow__steps")

    def _require_flow(self, document: Document):
        flow = getattr(document, "validation_flow", None)
        if not flow:
            raise ValidationError(
                "El documento no tiene un flujo de validación asociado."
            )
        return flow

    def _get_first_pending_step(self, document: Document):
        flow = self._require_flow(document)
        step = (
            flow.steps.select_for_update()
            .filter(status=ValidationStatus.PENDING)
            .order_by("order", "created_at")
            .first()
        )
        if step is None:
            raise ValidationError("No existen pasos pendientes para este documento.")
        return step

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        company = serializer.validated_data["company"]
        bucket_name = default_bucket_name()
        bucket_key = build_document_bucket_key(
            company_id=company.id, filename=serializer.validated_data["name"]
        )

        flow_data = serializer.validated_data.get("validation_flow")
        validation_status = (
            ValidationStatus.PENDING if flow_data is not None else None
        )

        document = serializer.save(
            created_by=request.user,
            bucket_name=bucket_name,
            bucket_key=bucket_key,
            validation_status=validation_status,
        )

        upload_url = generate_upload_signed_url(
            bucket_name=document.bucket_name,
            bucket_key=document.bucket_key,
            mime_type=document.mime_type,
        )

        response_data = {
            "document": self.get_serializer(document).data,
            "upload_url": upload_url,
        }
        headers = self.get_success_headers(response_data["document"])
        return Response(response_data, status=status.HTTP_201_CREATED, headers=headers)

    @action(detail=True, methods=["get"], url_path="download")
    def download(self, request, *args, **kwargs):
        document = self.get_object()
        url = generate_download_signed_url(
            bucket_name=document.bucket_name, bucket_key=document.bucket_key
        )
        return Response({"download_url": url})

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, *args, **kwargs):
        document = self.get_object()

        if document.validation_status == ValidationStatus.REJECTED:
            raise ValidationError("El documento ya fue rechazado y no puede aprobarse.")

        actor_user_id = request.data.get("actor_user_id")
        if not actor_user_id:
            raise ValidationError({"actor_user_id": "Este campo es obligatorio."})

        if str(request.user.id) != str(actor_user_id):
            raise ValidationError(
                {"actor_user_id": "Debe coincidir con el usuario autenticado."}
            )

        reason = request.data.get("reason", "")

        with transaction.atomic():
            step = self._get_first_pending_step(document)
            self.check_object_permissions(request, step)

            if step.status == ValidationStatus.REJECTED:
                raise ValidationError("El paso fue rechazado y no puede aprobarse.")

            now = timezone.now()

            step.status = ValidationStatus.APPROVED
            step.reason = reason or ""
            step.action_date = now
            step.save(update_fields=["status", "reason", "action_date", "updated_at"])

            flow = document.validation_flow
            flow.steps.filter(
                order__gt=step.order,
                status=ValidationStatus.PENDING,
            ).update(
                status=ValidationStatus.APPROVED,
                action_date=now,
                updated_at=now,
            )

            remaining_pending = flow.steps.filter(status=ValidationStatus.PENDING).exists()

            document.validation_status = (
                ValidationStatus.PENDING if remaining_pending else ValidationStatus.APPROVED
            )
            document.save(update_fields=["validation_status", "updated_at"])

        refreshed = self.get_queryset().get(pk=document.pk)
        return Response(self.get_serializer(refreshed).data)

    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, *args, **kwargs):
        document = self.get_object()

        if document.validation_status == ValidationStatus.APPROVED:
            raise ValidationError("El documento ya fue aprobado y no puede rechazarse.")

        actor_user_id = request.data.get("actor_user_id")
        if not actor_user_id:
            raise ValidationError({"actor_user_id": "Este campo es obligatorio."})

        if str(request.user.id) != str(actor_user_id):
            raise ValidationError(
                {"actor_user_id": "Debe coincidir con el usuario autenticado."}
            )

        reason = request.data.get("reason", "")

        with transaction.atomic():
            step = self._get_first_pending_step(document)
            self.check_object_permissions(request, step)

            now = timezone.now()

            step.status = ValidationStatus.REJECTED
            step.reason = reason or ""
            step.action_date = now
            step.save(update_fields=["status", "reason", "action_date", "updated_at"])

            document.validation_status = ValidationStatus.REJECTED
            document.save(update_fields=["validation_status", "updated_at"])

        refreshed = self.get_queryset().get(pk=document.pk)
        return Response(self.get_serializer(refreshed).data, status=status.HTTP_200_OK)
