"""Servicios utilitarios para la gestión de documentos."""

from __future__ import annotations

from datetime import timedelta
from typing import Optional

from django.conf import settings
from google.cloud import storage


def _build_storage_client() -> storage.Client:
    """Crea un cliente de Google Cloud Storage respetando las credenciales configuradas."""

    kwargs: dict = {"project": getattr(settings, "GS_PROJECT_ID", None)}
    credentials = getattr(settings, "GS_CREDENTIALS", None)
    if credentials is not None:
        kwargs["credentials"] = credentials
    return storage.Client(**{k: v for k, v in kwargs.items() if v is not None})


def generate_signed_url(
    *,
    bucket_key: str,
    method: str,
    content_type: Optional[str] = None,
    expires_in: Optional[int] = None,
) -> str:
    """Genera una URL firmada para un blob del bucket configurado."""

    client = _build_storage_client()
    bucket_name = getattr(settings, "GS_BUCKET_NAME")
    expiration = timedelta(seconds=expires_in or getattr(settings, "GS_EXPIRATION", 900))

    bucket = client.bucket(bucket_name)
    blob = bucket.blob(bucket_key)
    return blob.generate_signed_url(
        expiration=expiration,
        method=method,
        content_type=content_type,
        version="v4",
    )


def generate_upload_signed_url(*, bucket_key: str, mime_type: Optional[str] = None) -> str:
    """Genera una URL firmada de subida (método PUT)."""

    return generate_signed_url(bucket_key=bucket_key, method="PUT", content_type=mime_type)


def generate_download_signed_url(*, bucket_key: str) -> str:
    """Genera una URL firmada de descarga (método GET)."""

    return generate_signed_url(bucket_key=bucket_key, method="GET")
