"""Modelos de la aplicación de documentos."""

import uuid

from django.conf import settings
from django.db import models


class TimeStampedUUIDModel(models.Model):
    """Modelo base con clave primaria UUID y campos de auditoría."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Company(TimeStampedUUIDModel):
    """Entidad que representa una compañía dueña de documentos."""

    name = models.CharField(max_length=255)
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="CompanyMembership",
        related_name="companies",
        blank=True,
    )

    def __str__(self) -> str:  # pragma: no cover - representación simple
        return self.name


class EntityReference(TimeStampedUUIDModel):
    """Referencia hacia una entidad externa en el sistema."""

    entity_type = models.CharField(max_length=100)
    external_identifier = models.CharField(max_length=255)

    def __str__(self) -> str:  # pragma: no cover - representación simple
        return f"{self.entity_type}: {self.external_identifier}"


class ValidationStatus(models.TextChoices):
    PENDING = "P", "Pendiente"
    APPROVED = "A", "Aprobado"
    REJECTED = "R", "Rechazado"


class Document(TimeStampedUUIDModel):
    """Documento almacenado en el sistema."""

    name = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=100)
    size = models.PositiveBigIntegerField()
    file_hash = models.CharField(max_length=128, blank=True, null=True)
    bucket_name = models.CharField(max_length=255)
    bucket_key = models.CharField(max_length=255)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="documents"
    )
    entity_reference = models.ForeignKey(
        EntityReference, on_delete=models.CASCADE, related_name="documents"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documents",
    )
    validation_status = models.CharField(
        max_length=1,
        choices=ValidationStatus.choices,
        blank=True,
        null=True,
    )

    def __str__(self) -> str:  # pragma: no cover - representación simple
        return self.name


class ValidationFlow(TimeStampedUUIDModel):
    """Flujo de validación asociado a un documento."""

    document = models.OneToOneField(
        Document, on_delete=models.CASCADE, related_name="validation_flow"
    )

    def __str__(self) -> str:  # pragma: no cover - representación simple
        return f"Flujo de validación para {self.document_id}"


class ValidationStep(TimeStampedUUIDModel):
    """Paso individual dentro de un flujo de validación."""

    flow = models.ForeignKey(
        ValidationFlow, on_delete=models.CASCADE, related_name="steps"
    )
    order = models.PositiveIntegerField()
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="validation_steps",
    )
    status = models.CharField(
        max_length=1,
        choices=ValidationStatus.choices,
        default=ValidationStatus.PENDING,
    )
    reason = models.TextField(blank=True)
    action_date = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["order", "created_at"]

    def __str__(self) -> str:  # pragma: no cover - representación simple
        return f"Paso {self.order} - {self.get_status_display()}"

class CompanyMembership(TimeStampedUUIDModel):
    """Relación entre usuarios y compañías a las que pertenecen."""

    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="memberships"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="company_memberships",
    )

    class Meta:
        unique_together = ("company", "user")

    def __str__(self) -> str:  # pragma: no cover - representación simple
        return f"{self.user_id} -> {self.company_id}"
        

class PendingDocumentUpload(TimeStampedUUIDModel):
    """Carga de documento aún no confirmada en el bucket."""

    name = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=100)
    size = models.PositiveBigIntegerField()
    file_hash = models.CharField(max_length=128, blank=True, null=True)
    bucket_name = models.CharField(max_length=255)
    bucket_key = models.CharField(max_length=255, unique=True)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="pending_uploads"
    )
    entity_reference = models.ForeignKey(
        EntityReference, on_delete=models.CASCADE, related_name="pending_uploads"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="pending_document_uploads",
    )
    validation_steps = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:  # pragma: no cover - representación simple
        return f"Carga pendiente de {self.name}"
