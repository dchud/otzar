from typing import ClassVar

from django.contrib import admin

from ingest.models import APIUsageLog, ScanResult


@admin.register(ScanResult)
class ScanResultAdmin(admin.ModelAdmin):
    list_display: ClassVar[list[str]] = [
        "scan_type",
        "status",
        "isbn",
        "scanned_by",
        "created_at",
    ]
    list_filter: ClassVar[list[str]] = ["scan_type", "status"]
    readonly_fields: ClassVar[list[str]] = ["created_at", "updated_at"]


@admin.register(APIUsageLog)
class APIUsageLogAdmin(admin.ModelAdmin):
    list_display: ClassVar[list[str]] = [
        "api",
        "model",
        "user",
        "input_tokens",
        "output_tokens",
        "created_at",
    ]
    list_filter: ClassVar[list[str]] = ["api", "model"]
    readonly_fields: ClassVar[list[str]] = ["created_at"]
