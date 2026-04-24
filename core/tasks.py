import random
from celery import shared_task
from django.db import transaction
from django.utils import timezone
from .models import Payout, LedgerEntry, PayoutStatus

@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def process_payout_task(self, payout_id):
    payout = Payout.objects.get(id=payout_id)
    
    # We only process if it is pending or processing (on retry)
    if payout.status not in [PayoutStatus.PENDING, PayoutStatus.PROCESSING]:
        return f"Cannot process payout in {payout.status} state"
        
    if payout.status == PayoutStatus.PENDING:
        payout.status = PayoutStatus.PROCESSING
        payout.save()

    # Simulate bank settlement
    outcome = random.choices(['success', 'fail', 'hang'], weights=[0.7, 0.2, 0.1])[0]
    
    if outcome == 'success':
        payout.status = PayoutStatus.COMPLETED
        payout.save()
        return f"Payout {payout_id} completed"
        
    elif outcome == 'fail':
        # Failure means we must return funds atomically
        with transaction.atomic():
            # Refresh to make sure
            payout.refresh_from_db()
            if payout.status != PayoutStatus.PROCESSING:
                return "State changed during failure simulation"

            payout.status = PayoutStatus.FAILED
            payout.save()
            
            # Return funds with a credit
            LedgerEntry.objects.create(
                merchant=payout.merchant,
                entry_type=LedgerEntry.EntryType.CREDIT,
                amount_paise=payout.amount_paise,
                payout=payout,
                description="Refund for failed payout"
            )
        return f"Payout {payout_id} failed, funds returned"
        
    elif outcome == 'hang':
        # Simulate timeout and let celery retry it with backoff
        # The backoff is handled by celery self.retry
        try:
            # 2^retries * 5 seconds
            countdown = 5 * (2 ** self.request.retries)
            self.retry(countdown=countdown)
        except self.MaxRetriesExceededError:
            # Max retries hit, fail the payout
            with transaction.atomic():
                payout.refresh_from_db()
                if payout.status == PayoutStatus.PROCESSING:
                    payout.status = PayoutStatus.FAILED
                    payout.save()
                    LedgerEntry.objects.create(
                        merchant=payout.merchant,
                        entry_type=LedgerEntry.EntryType.CREDIT,
                        amount_paise=payout.amount_paise,
                        payout=payout,
                        description="Refund for timeout max retries payout"
                    )
            return f"Payout {payout_id} failed after max retries"
