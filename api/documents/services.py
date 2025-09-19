"""Servicios utilitarios para la gestión de documentos."""

from __future__ import annotations
import uuid
from pathlib import Path

from django.conf import settings

from .storage_service import (
    generate_download_signed_url,
    generate_signed_url,
    generate_upload_signed_url,
)

def build_document_bucket_key(*, company_id, filename: str) -> str:
    """Genera una ruta única de almacenamiento para un documento."""

    extension = Path(filename).suffix.lower()
    unique_token = uuid.uuid4().hex
    return f"companies/{company_id}/documents/{unique_token}{extension}"


def default_bucket_name() -> str:
    """Retorna el nombre del bucket configurado en el proyecto."""

    return getattr(settings, "GS_BUCKET_NAME")

__all__ = [
    "build_document_bucket_key",
    "default_bucket_name",
    "generate_signed_url",
    "generate_upload_signed_url",
    "generate_download_signed_url",
]