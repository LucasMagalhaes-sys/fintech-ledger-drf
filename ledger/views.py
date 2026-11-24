from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from .models import Account, Transaction
from .serializers import AccountSerializer, TransactionSerializer, TransferRequestSerializer
from .services import execute_transfer


class AccountViewSet(viewsets.ModelViewSet):
    serializer_class = AccountSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Account.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class TransactionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = TransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user_accounts = Account.objects.filter(owner=self.request.user)
        return (
            Transaction.objects.filter(source_account__in=user_accounts)
            | Transaction.objects.filter(target_account__in=user_accounts)
        ).distinct()

    @extend_schema(request=TransferRequestSerializer, responses={201: TransactionSerializer})
    def create(self, request, *args, **kwargs):
        input_serializer = TransferRequestSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)

        try:
            tx = execute_transfer(user=request.user, **input_serializer.validated_data)
        except DjangoValidationError as exc:
            raise ValidationError({"detail": exc.message})

        output_serializer = TransactionSerializer(tx)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)
