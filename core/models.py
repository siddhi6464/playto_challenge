from django.db import models
from django.core.exceptions import ValidationError

class Merchant(models.Model):
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class PayoutStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    PROCESSING = 'processing', 'Processing'
    COMPLETED = 'completed', 'Completed'
    FAILED = 'failed', 'Failed'

class Payout(models.Model):
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name='payouts')
    amount_paise = models.BigIntegerField()
    bank_account_id = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=PayoutStatus.choices, default=PayoutStatus.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    retry_count = models.IntegerField(default=0)

    def clean(self):
        # Validate state machine. Ensure backwards transitions are impossible.
        if self.pk:
            old_payout = Payout.objects.get(pk=self.pk)
            old_status = old_payout.status
            
            invalid_transitions = [
                (PayoutStatus.COMPLETED, PayoutStatus.PENDING),
                (PayoutStatus.COMPLETED, PayoutStatus.PROCESSING),
                (PayoutStatus.COMPLETED, PayoutStatus.FAILED),
                (PayoutStatus.FAILED, PayoutStatus.PENDING),
                (PayoutStatus.FAILED, PayoutStatus.PROCESSING),
                (PayoutStatus.FAILED, PayoutStatus.COMPLETED),
            ]
            if (old_status, self.status) in invalid_transitions:
                raise ValidationError(f"Invalid state transition from {old_status} to {self.status}")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

class LedgerEntry(models.Model):
    class EntryType(models.TextChoices):
        CREDIT = 'credit', 'Credit'
        DEBIT = 'debit', 'Debit'

    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name='ledger_entries')
    entry_type = models.CharField(max_length=10, choices=EntryType.choices)
    amount_paise = models.BigIntegerField()
    payout = models.ForeignKey(Payout, on_delete=models.SET_NULL, null=True, blank=True, related_name='ledger_entries')
    description = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class IdempotencyKey(models.Model):
    key = models.UUIDField(db_index=True)
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE)
    response_status = models.IntegerField(null=True, blank=True)
    response_body = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('key', 'merchant')
