from decimal import Decimal
import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from ledger.models import Account, Transaction

User = get_user_model()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def users_and_accounts(db):
    alice = User.objects.create_user(username="alice", password="strongpassword123")
    bob = User.objects.create_user(username="bob", password="strongpassword123")

    alice_acc = Account.objects.create(owner=alice, currency="EUR", balance=Decimal("500.00"))
    bob_acc = Account.objects.create(owner=bob, currency="EUR", balance=Decimal("100.00"))
    return alice, bob, alice_acc, bob_acc


def test_atomic_transfer_success(api_client, users_and_accounts):
    alice, _, alice_acc, bob_acc = users_and_accounts
    api_client.force_authenticate(user=alice)

    payload = {
        "source_account_id": str(alice_acc.id),
        "target_account_id": str(bob_acc.id),
        "amount": "150.00",
        "idempotency_key": "tx-001",
    }
    response = api_client.post("/api/v1/transactions/", payload, format="json")

    assert response.status_code == 201
    alice_acc.refresh_from_db()
    bob_acc.refresh_from_db()
    assert alice_acc.balance == Decimal("350.00")
    assert bob_acc.balance == Decimal("250.00")


def test_idempotency_prevents_double_charge(api_client, users_and_accounts):
    alice, _, alice_acc, bob_acc = users_and_accounts
    api_client.force_authenticate(user=alice)

    payload = {
        "source_account_id": str(alice_acc.id),
        "target_account_id": str(bob_acc.id),
        "amount": "100.00",
        "idempotency_key": "tx-idempotent-999",
    }
    first_res = api_client.post("/api/v1/transactions/", payload, format="json")
    second_res = api_client.post("/api/v1/transactions/", payload, format="json")

    assert first_res.status_code == 201
    assert second_res.status_code == 201
    assert first_res.data["id"] == second_res.data["id"]
    assert Transaction.objects.count() == 1

    alice_acc.refresh_from_db()
    assert alice_acc.balance == Decimal("400.00")


def test_insufficient_funds_rejected(api_client, users_and_accounts):
    alice, _, alice_acc, bob_acc = users_and_accounts
    api_client.force_authenticate(user=alice)

    payload = {
        "source_account_id": str(alice_acc.id),
        "target_account_id": str(bob_acc.id),
        "amount": "999.00",
        "idempotency_key": "tx-fail-funds",
    }
    response = api_client.post("/api/v1/transactions/", payload, format="json")

    assert response.status_code == 400
    alice_acc.refresh_from_db()
    assert alice_acc.balance == Decimal("500.00")


def test_cannot_debit_another_users_account(api_client, users_and_accounts):
    alice, _, alice_acc, bob_acc = users_and_accounts
    api_client.force_authenticate(user=alice)

    payload = {
        "source_account_id": str(bob_acc.id),
        "target_account_id": str(alice_acc.id),
        "amount": "50.00",
        "idempotency_key": "tx-unauthorized",
    }
    response = api_client.post("/api/v1/transactions/", payload, format="json")

    assert response.status_code == 400
    bob_acc.refresh_from_db()
    assert bob_acc.balance == Decimal("100.00")
