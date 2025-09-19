"""Permisos personalizados para la API de documentos."""

from __future__ import annotations
from typing import Any
from rest_framework.permissions import BasePermission
from .models import (
    Company,
    CompanyMembership,
    Document,
    PendingDocumentUpload,
    ValidationStep,
)


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
        if view.action == "complete_upload":
            return True
        return True

    def has_object_permission(self, request, view, obj: Any) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False

        company: Company | None = None
        if isinstance(obj, Document):
            company = obj.company
        elif isinstance(obj, ValidationStep):
            company = obj.flow.document.company
        elif hasattr(obj, "company"):
            company = getattr(obj, "company")

        if company is None:
            return False

        return CompanyMembership.objects.filter(company=company, user=user).exists()


class IsStepApprover(BasePermission):
    """Restringe operaciones a los usuarios asignados como aprobadores del paso."""

    message = "El usuario no está autorizado para operar sobre este paso."
    restricted_actions = {"approve", "reject"}

    def has_permission(self, request, view) -> bool:
        return True

    def has_object_permission(self, request, view, obj: Any) -> bool:
        if getattr(view, "action", None) not in self.restricted_actions:
            return True

        if isinstance(obj, ValidationStep):
            user = request.user
            return bool(user and user.is_authenticated and obj.approver_id == user.id)

        return True
