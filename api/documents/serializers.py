"""Serializadores para la aplicación de documentos."""

from __future__ import annotations

from typing import Iterable, List

from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import (
    Company,
    Document,
    EntityReference,
    ValidationFlow,
    ValidationStep,
    ValidationStatus,
)
from .services import (
    build_document_bucket_key,
    create_document_with_flow,
    default_bucket_name,
    normalize_flow_steps,
)

DEFAULT_ALLOWED_MIME_TYPES: Iterable[str] = (
    "application/pdf",
    "image/jpeg",
    "image/png",
)
DEFAULT_MAX_FILE_SIZE: int = 20 * 1024 * 1024  # 20 MB


class CompanySerializer(serializers.ModelSerializer):
    """Serializer para el modelo :class:`Company`."""

    class Meta:
        model = Company
        fields = ["id", "name", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class EntityReferenceSerializer(serializers.ModelSerializer):
    """Serializer para el modelo :class:`EntityReference`."""

    class Meta:
        model = EntityReference
        fields = [
            "id",
            "entity_type",
            "external_identifier",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class ValidationStepSerializer(serializers.ModelSerializer):
    """Serializer para cada paso del flujo de validación."""

    approver = serializers.PrimaryKeyRelatedField(
        queryset=get_user_model().objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = ValidationStep
        fields = [
            "id",
            "flow",
            "order",
            "approver",
            "status",
            "reason",
            "action_date",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "flow", "created_at", "updated_at"]


class ValidationFlowSerializer(serializers.ModelSerializer):
    """Serializer para un flujo de validación."""

    steps = ValidationStepSerializer(many=True)

    class Meta:
        model = ValidationFlow
        fields = ["id", "document", "steps", "created_at", "updated_at"]
        read_only_fields = ["id", "document", "created_at", "updated_at"]

    def validate_steps(self, value: List[dict]) -> List[dict]:
        """Valida que la colección de pasos no esté vacía y sus órdenes sean únicos."""

        if not value:
            raise serializers.ValidationError("Debe registrar al menos un paso.")

        orders = [step.get("order") for step in value]
        if len(orders) != len(set(orders)):
            raise serializers.ValidationError(
                "El valor del campo 'order' debe ser único por paso."
            )

        return value

    def create(self, validated_data: dict) -> ValidationFlow:
        steps_data = validated_data.pop("steps", [])
        flow = ValidationFlow.objects.create(**validated_data)
        for step_data in steps_data:
            ValidationStep.objects.create(flow=flow, **step_data)
        return flow


class DocumentSerializer(serializers.ModelSerializer):
    """Serializer del modelo :class:`Document` con validaciones personalizadas."""

    company = serializers.PrimaryKeyRelatedField(queryset=Company.objects.all())
    entity_reference = serializers.PrimaryKeyRelatedField(
        queryset=EntityReference.objects.all()
    )
    created_by = serializers.PrimaryKeyRelatedField(
        queryset=get_user_model().objects.all(), required=False, allow_null=True
    )
    validation_flow = ValidationFlowSerializer(required=False)

    class Meta:
        model = Document
        fields = [
            "id",
            "name",
            "mime_type",
            "size",
            "file_hash",
            "bucket_name",
            "bucket_key",
            "company",
            "entity_reference",
            "created_by",
            "validation_status",
            "validation_flow",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "bucket_name",
            "bucket_key",
            "validation_status",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {
            "name": {"required": True},
            "mime_type": {"required": True},
            "size": {"required": True},
            "company": {"required": True},
            "entity_reference": {"required": True},
        }

    def _allowed_mime_types(self) -> Iterable[str]:
        return getattr(
            settings,
            "DOCUMENTS_ALLOWED_MIME_TYPES",
            DEFAULT_ALLOWED_MIME_TYPES,
        )

    def _max_file_size(self) -> int:
        return getattr(settings, "DOCUMENTS_MAX_FILE_SIZE", DEFAULT_MAX_FILE_SIZE)

    def validate_mime_type(self, value: str) -> str:
        allowed_types = set(self._allowed_mime_types())
        if value not in allowed_types:
            allowed_display = ", ".join(sorted(allowed_types))
            raise serializers.ValidationError(
                f"Tipo MIME no permitido. Tipos permitidos: {allowed_display}."
            )
        return value

    def validate_size(self, value: int) -> int:
        if value <= 0:
            raise serializers.ValidationError(
                "El tamaño del archivo debe ser un entero positivo."
            )

        max_size = self._max_file_size()
        if value > max_size:
            raise serializers.ValidationError(
                f"El tamaño del archivo supera el máximo permitido de {max_size} bytes."
            )
        return value

    def validate_validation_flow(self, value: dict) -> dict:
        if value is None:
            return value
        # El serializer anidado ya gestiona las validaciones específicas.
        return value

    def create(self, validated_data: dict) -> Document:
        flow_data = validated_data.pop("validation_flow", None)
        steps_data = []
        if flow_data is not None:
            steps_data = flow_data.pop("steps", [])
   

        validated_data.setdefault("bucket_name", default_bucket_name())
        if "bucket_key" not in validated_data:
            company = validated_data["company"]
            validated_data["bucket_key"] = build_document_bucket_key(
                company_id=company.id,
                filename=validated_data["name"],
            )
    

    

        normalized_steps = normalize_flow_steps(steps_data)

        if normalized_steps and not validated_data.get("validation_status"):
            validated_data["validation_status"] = ValidationStatus.PENDING

        return create_document_with_flow(
            validation_steps=normalized_steps,
            **validated_data,
        )     

    def update(self, instance: Document, validated_data: dict) -> Document:
        # No se gestionan modificaciones del flujo desde este serializer.
        validated_data.pop("validation_flow", None)
        return super().update(instance, validated_data)