"""Permisos personalizados para la API de documentos."""

from __future__ import annotations

from typing import Any

from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission

from .models import Company, CompanyMembership, Document


class IsCompanyMember(BasePermission):
    """Permite acceso solo a usuarios pertenecientes a la compañía del documento."""

    message = "El usuario no pertenece a la compañía solicitada."

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False

        if view.action == "create":
            company_id = request.data.get("company")
            if not company_id:
                return False
            return CompanyMembership.objects.filter(
                company_id=company_id, user=user
            ).exists()
        return True

    def has_object_permission(self, request, view, obj: Any) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False

        company: Company | None = None
        if isinstance(obj, Document):
            company = obj.company
        elif hasattr(obj, "company"):
            company = getattr(obj, "company")

        if company is None:
            return False

        return CompanyMembership.objects.filter(company=company, user=user).exists()


class IsStepApprover(BasePermission):
    """Permiso auxiliar para validar si el usuario es aprobador del paso."""

    message = "El usuario no está autorizado para operar sobre este paso."

    def ensure_user_is_step_approver(self, request, step: Any) -> None:
        user = request.user
        if not user or not user.is_authenticated or step.approver_id != user.id:
            raise PermissionDenied(self.message)

    def has_permission(self, request, view) -> bool:  # pragma: no cover - controlado manualmente
        return True

    def has_object_permission(self, request, view, obj: Document) -> bool:  # pragma: no cover - no usado directamente
        return True