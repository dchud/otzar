from django.contrib import admin

from ingest.models import APIUsageLog, ScanResult


@admin.register(ScanResult)
class ScanResultAdmin(admin.ModelAdmin):
    list_display = ["scan_type", "status", "isbn", "scanned_by", "created_at"]
    list_filter = ["scan_type", "status"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(APIUsageLog)
class APIUsageLogAdmin(admin.ModelAdmin):
    list_display = [
        "api",
        "model",
        "user",
        "input_tokens",
        "output_tokens",
        "created_at",
    ]
    list_filter = ["api", "model"]
    readonly_fields = ["created_at"]
