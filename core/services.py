from django.db import transaction, IntegrityError
from django.db.models import Sum, Case, When, F
from django.core.exceptions import ValidationError
from datetime import timedelta
from django.utils import timezone
from .models import Merchant, LedgerEntry, Payout, IdempotencyKey

def get_merchant_balance(merchant):
    """
    Returns (available_balance, held_balance).
    available = SUM(credits) - SUM(debits)
    held = SUM(debits linked to pending/processing payouts)
    """
    aggs = LedgerEntry.objects.filter(merchant=merchant).aggregate(
        total_credit=Sum(Case(When(entry_type=LedgerEntry.EntryType.CREDIT, then=F('amount_paise')), default=0)),
        total_debit=Sum(Case(When(entry_type=LedgerEntry.EntryType.DEBIT, then=F('amount_paise')), default=0)),
        held=Sum(Case(When(
            payout__status__in=['pending', 'processing'], 
            entry_type=LedgerEntry.EntryType.DEBIT, 
            then=F('amount_paise')
        ), default=0))
    )
    
    total_credit = aggs['total_credit'] or 0
    total_debit = aggs['total_debit'] or 0
    held = aggs['held'] or 0
    
    available = total_credit - total_debit
    return available, held

def process_payout_request(merchant_id, idempotency_key, amount_paise, bank_account_id):
    """
    Handles idempotency, concurrency locking, and balance checking.
    """
    # 1. Idempotency Check
    try:
        with transaction.atomic():
            idem_key_obj, created = IdempotencyKey.objects.get_or_create(
                key=idempotency_key,
                merchant_id=merchant_id,
            )
    except IntegrityError:
        # Race condition on get_or_create
        idem_key_obj = IdempotencyKey.objects.get(key=idempotency_key, merchant_id=merchant_id)
        created = False

    if not created:
        # Check if expired (24 hours)
        if timezone.now() - idem_key_obj.created_at > timedelta(hours=24):
            # Safe to overwrite or we could raise an error. Often just treated as a new request or expired error.
            raise ValueError("Idempotency key expired or invalid.")
            
        if idem_key_obj.response_status is None:
            raise ValueError("Concurrent request in flight for this key.")
        return {'status_code': idem_key_obj.response_status, 'data': idem_key_obj.response_body}

    # 2. Concurrency Lock & Balance Check
    try:
        with transaction.atomic():
            # select_for_update prevents concurrent payouts from overdrawing the balance.
            merchant = Merchant.objects.select_for_update().get(id=merchant_id)
            
            # Fetch derived balance
            available, held = get_merchant_balance(merchant)
            
            if available < amount_paise:
                raise ValidationError("Insufficient balance")
                
            # 3. Create Payout as pending
            payout = Payout.objects.create(
                merchant=merchant,
                amount_paise=amount_paise,
                bank_account_id=bank_account_id,
                status='pending'
            )
            
            # 4. Create LedgerEntry (Debit)
            LedgerEntry.objects.create(
                merchant=merchant,
                entry_type=LedgerEntry.EntryType.DEBIT,
                amount_paise=amount_paise,
                payout=payout,
                description="Payout Debit"
            )
    except Exception as e:
        # Failed, must clean up idempotency key since it failed, or return an error response
        idem_key_obj.response_status = 400
        idem_key_obj.response_body = {'error': str(e)}
        idem_key_obj.save()
        raise

    from .serializers import PayoutSerializer
    resp_data = PayoutSerializer(payout).data
    
    idem_key_obj.response_status = 201
    idem_key_obj.response_body = resp_data
    idem_key_obj.save()
    
    # Needs to trigger the background job
    from .tasks import process_payout_task
    transaction.on_commit(lambda: process_payout_task.delay(payout.id))

    return {'status_code': 201, 'data': resp_data}
