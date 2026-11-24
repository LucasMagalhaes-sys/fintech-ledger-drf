from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction
from .models import Account, Transaction


@transaction.atomic
def execute_transfer(
    *,
    user,
    source_account_id: str,
    target_account_id: str,
    amount: Decimal,
    idempotency_key: str,
) -> Transaction:
    existing = Transaction.objects.filter(idempotency_key=idempotency_key).first()
    if existing:
        return existing

    if str(source_account_id) == str(target_account_id):
        raise ValidationError("Source and target accounts must be different.")

    if amount <= Decimal("0.00"):
        raise ValidationError("Transfer amount must be positive.")

    account_ids = sorted([str(source_account_id), str(target_account_id)])
    locked_accounts = {
        str(acc.id): acc
        for acc in Account.objects.select_for_update().filter(id__in=account_ids, is_active=True)
    }

    source = locked_accounts.get(str(source_account_id))
    target = locked_accounts.get(str(target_account_id))

    if not source or not target:
        raise ValidationError("One or both accounts were not found or are inactive.")

    if source.owner != user:
        raise ValidationError("You do not have permission to debit from this account.")

    if source.currency != target.currency:
        raise ValidationError("Cross-currency transfers are not supported in this endpoint.")

    if source.balance < amount:
        raise ValidationError("Insufficient funds.")

    source.balance -= amount
    target.balance += amount
    source.save(update_fields=["balance"])
    target.save(update_fields=["balance"])

    return Transaction.objects.create(
        idempotency_key=idempotency_key,
        source_account=source,
        target_account=target,
        amount=amount,
        status=Transaction.Status.COMPLETED,
    )
