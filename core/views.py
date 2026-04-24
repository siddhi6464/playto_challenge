from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import ValidationError
from .models import Merchant, Payout
from .services import get_merchant_balance, process_payout_request
from .serializers import PayoutSerializer

class MerchantBalanceView(APIView):
    def get(self, request, pk):
        try:
            merchant = Merchant.objects.get(pk=pk)
            available, held = get_merchant_balance(merchant)
            return Response({
                'merchant_id': merchant.id,
                'available_balance_paise': available,
                'held_balance_paise': held
            })
        except Merchant.DoesNotExist:
            return Response({'error': 'Merchant not found'}, status=status.HTTP_404_NOT_FOUND)

class PayoutListCreateView(APIView):
    def get(self, request):
        merchant_id = request.query_params.get('merchant_id')
        if not merchant_id:
            return Response({'error': 'merchant_id required'}, status=status.HTTP_400_BAD_REQUEST)
        
        payouts = Payout.objects.filter(merchant_id=merchant_id).order_by('-created_at')
        return Response(PayoutSerializer(payouts, many=True).data)

    def post(self, request):
        idempotency_key = request.headers.get('Idempotency-Key')
        if not idempotency_key:
            return Response({'error': 'Idempotency-Key header is required'}, status=status.HTTP_400_BAD_REQUEST)

        merchant_id = request.data.get('merchant_id')
        amount_paise = request.data.get('amount_paise')
        bank_account_id = request.data.get('bank_account_id')

        if not all([merchant_id, amount_paise, bank_account_id]):
            return Response({'error': 'Missing required fields'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            amount_paise = int(amount_paise)
            if amount_paise <= 0:
                raise ValueError("Amount must be positive")
        except ValueError:
            return Response({'error': 'Invalid amount_paise'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            result = process_payout_request(merchant_id, idempotency_key, amount_paise, bank_account_id)
            return Response(result['data'], status=result['status_code'])
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except ValueError as e:
            # specifically for idempotency errors etc.
            return Response({'error': str(e)}, status=status.HTTP_409_CONFLICT)
        except Exception as e:
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
