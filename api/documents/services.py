"""Servicios utilitarios para la gestión de documentos."""

from __future__ import annotations
import uuid
from pathlib import Path
from typing import List, Mapping, MutableMapping, Sequence
from django.conf import settings

from .storage_service import (
    blob_exists,
    generate_download_signed_url,
    generate_signed_url,
    generate_upload_signed_url,
)
from .models import Document, ValidationFlow, ValidationStep, ValidationStatus

def build_document_bucket_key(*, company_id, filename: str) -> str:
    """Genera una ruta única de almacenamiento para un documento."""

    extension = Path(filename).suffix.lower()
    unique_token = uuid.uuid4().hex
    return f"companies/{company_id}/documents/{unique_token}{extension}"


def default_bucket_name() -> str:
    """Retorna el nombre del bucket configurado en el proyecto."""

    return getattr(settings, "GS_BUCKET_NAME")

def normalize_flow_steps(steps: Sequence[Mapping[str, object]]) -> List[dict]:
    """Normaliza los datos de pasos para facilitar su persistencia."""

    normalized: List[dict] = []
    for step in steps:
        order = step.get("order")
        approver = step.get("approver")
        approver_id = step.get("approver_id")
        if approver is not None and approver_id is None:
            approver_id = getattr(approver, "id", None)

        normalized.append({
            "order": order,
            "approver_id": str(approver_id) if approver_id is not None else None,
        })
    return normalized


def create_document_with_flow(
    *,
    validation_steps: Sequence[Mapping[str, object]] | None = None,
    **document_fields: MutableMapping[str, object],
) -> Document:
    """Crea un documento y, opcionalmente, su flujo de validación asociado."""

    steps: Sequence[Mapping[str, object]] = validation_steps or []

    if steps and not document_fields.get("validation_status"):
        document_fields["validation_status"] = ValidationStatus.PENDING

    document = Document.objects.create(**document_fields)

    if steps:
        flow = ValidationFlow.objects.create(document=document)
        for step in steps:
            order = step.get("order")
            approver_id = step.get("approver_id")
            ValidationStep.objects.create(
                flow=flow,
                order=order,
                approver_id=approver_id,
                status=ValidationStatus.PENDING,
            )

    return document



__all__ = [
    "build_document_bucket_key",
    "default_bucket_name",
    "generate_signed_url",
    "generate_upload_signed_url",
    "generate_download_signed_url",
    "normalize_flow_steps",
    "create_document_with_flow",
    "blob_exists",
]