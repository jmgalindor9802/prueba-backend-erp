"""Servicios de almacenamiento en Google Cloud Storage."""

from __future__ import annotations

from datetime import timedelta
from typing import Optional

from django.conf import settings
from google.cloud import storage


def _build_storage_client() -> storage.Client:
    """Crea un cliente de Google Cloud Storage usando la configuración del proyecto."""

    project_id = getattr(settings, "GS_PROJECT_ID", None)
    credentials = getattr(settings, "GS_CREDENTIALS", None)

    client_kwargs: dict[str, object] = {}
    if project_id is not None:
        client_kwargs["project"] = project_id
    if credentials is not None:
        client_kwargs["credentials"] = credentials

    return storage.Client(**client_kwargs)


def _get_expiration(expires_in: Optional[int] = None) -> timedelta:
    """Calcula el periodo de expiración para las URLs firmadas."""

    seconds = expires_in or getattr(settings, "GS_EXPIRATION", 900)
    return timedelta(seconds=seconds)


def generate_signed_url(
    *,
    bucket_key: str,
    method: str,
    content_type: Optional[str] = None,
    expires_in: Optional[int] = None,
    bucket_name: Optional[str] = None,
) -> str:
    """Genera una URL firmada para el blob indicado."""

    client = _build_storage_client()
    resolved_bucket = bucket_name or getattr(settings, "GS_BUCKET_NAME")
    bucket = client.bucket(resolved_bucket)
    blob = bucket.blob(bucket_key)

    return blob.generate_signed_url(
        version="v4",
        expiration=_get_expiration(expires_in),
        method=method,
        content_type=content_type,
    )


def generate_upload_signed_url(
     *,
    bucket_key: str,
    mime_type: Optional[str] = None,
    expires_in: Optional[int] = None,
    bucket_name: Optional[str] = None,
) -> str:
    """Genera una URL firmada de subida usando el método HTTP PUT."""

    return generate_signed_url(
        bucket_key=bucket_key,
        method="PUT",
        content_type=mime_type,
        expires_in=expires_in,
        bucket_name=bucket_name,
    )


def generate_download_signed_url(
    *, bucket_key: str, expires_in: Optional[int] = None, bucket_name: Optional[str] = None
) -> str:
    """Genera una URL firmada de descarga usando el método HTTP GET."""

    return generate_signed_url(
        bucket_key=bucket_key,
        method="GET",
        expires_in=expires_in,
        bucket_name=bucket_name,
    )


__all__ = [
    "generate_signed_url",
    "generate_upload_signed_url",
    "generate_download_signed_url",
]