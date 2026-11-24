from rest_framework import serializers
from .models import Account, Transaction


class AccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account
        fields = ["id", "currency", "balance", "is_active", "created_at"]
        read_only_fields = ["id", "balance", "is_active", "created_at"]


class TransferRequestSerializer(serializers.Serializer):
    source_account_id = serializers.UUIDField()
    target_account_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    idempotency_key = serializers.CharField(max_length=64)


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = [
            "id",
            "idempotency_key",
            "source_account",
            "target_account",
            "amount",
            "status",
            "created_at",
        ]
