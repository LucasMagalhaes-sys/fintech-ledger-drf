from django.contrib import admin
from .models import Account, Transaction


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ("id", "owner", "currency", "balance", "is_active", "created_at")
    list_filter = ("currency", "is_active")
    search_fields = ("owner__username", "id")
    readonly_fields = ("id", "created_at")


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("id", "idempotency_key", "source_account", "target_account", "amount", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("idempotency_key", "id")
    readonly_fields = ("id", "created_at")
