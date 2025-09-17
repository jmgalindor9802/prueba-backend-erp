from django.contrib import admin
from .models import Document


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "reference_code", "created_at")
    list_filter = ("created_at",)
    search_fields = ("name", "reference_code")
