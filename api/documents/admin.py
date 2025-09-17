from django.contrib import admin

from .models import Company, Document, EntityReference, ValidationFlow, ValidationStep


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "created_at", "updated_at")
    search_fields = ("name",)


@admin.register(EntityReference)
class EntityReferenceAdmin(admin.ModelAdmin):
    list_display = ("id", "entity_type", "external_identifier", "created_at")
    search_fields = ("entity_type", "external_identifier")


class ValidationStepInline(admin.TabularInline):
    model = ValidationStep
    extra = 0
    readonly_fields = ("created_at", "updated_at")


@admin.register(ValidationFlow)
class ValidationFlowAdmin(admin.ModelAdmin):
    list_display = ("id", "document", "created_at", "updated_at")
    search_fields = ("document__name",)
    inlines = (ValidationStepInline,)


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "bucket_key", "validation_status", "created_at")
    list_filter = ("validation_status", "created_at")
    search_fields = ("name", "bucket_key")
    autocomplete_fields = ("company", "entity_reference", "created_by")


@admin.register(ValidationStep)
class ValidationStepAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "flow",
        "order",
        "approver",
        "status",
        "action_date",
        "created_at",
    )
    list_filter = ("status", "created_at", "action_date")
    search_fields = ("flow__document__name", "approver__username")
    autocomplete_fields = ("flow", "approver")
