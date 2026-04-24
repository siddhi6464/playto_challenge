# Playto Payout Engine Explainer

## 1. The Ledger
**Paste your balance calculation query.**
```python
aggs = LedgerEntry.objects.filter(merchant=merchant).aggregate(
    total_credit=Sum(Case(When(entry_type=LedgerEntry.EntryType.CREDIT, then=F('amount_paise')), default=0)),
    total_debit=Sum(Case(When(entry_type=LedgerEntry.EntryType.DEBIT, then=F('amount_paise')), default=0)),
    held=Sum(Case(When(
        payout__status__in=['pending', 'processing'], 
        entry_type=LedgerEntry.EntryType.DEBIT, 
        then=F('amount_paise')
    ), default=0))
)
available = (aggs['total_credit'] or 0) - (aggs['total_debit'] or 0)
```
**Why did you model credits and debits this way?**
I modeled the ledger as an append-only event log. `amount_paise` is strictly an absolute BigIntegerField, and the `entry_type` classifies it. Calculating the balance dynamically enforces single-source-of-truth integrity. Any static `balance` field on the merchant model introduces the risk of the cache getting out of sync with actual funds. If a payout fails, a credit is inserted rather than modifying/deleting the old debit, preserving the financial audit trail.

## 2. The Lock
**Paste the exact code that prevents two concurrent payouts from overdrawing a balance.**
```python
with transaction.atomic():
    merchant = Merchant.objects.select_for_update().get(id=merchant_id)
    available, held = get_merchant_balance(merchant)
    if available < amount_paise:
        raise ValidationError("Insufficient balance")
```
**Explain what database primitive it relies on.**
It relies on PostgreSQL's `SELECT ... FOR UPDATE` row-level lock. This instructs the DB engine to lock the `merchant` row until the current transaction commits or rolls back. Any concurrent request attempting to process a payout for the same merchant will block and wait at `select_for_update()`. When the first transaction finishes inserting its `debit` ledger entry and commits, its lock releases. The second transaction then wakes up, evaluates the latest ledger balance, and correctly observes the deducted amount.

## 3. The Idempotency
**How does your system know it has seen a key before?**
I use an `IdempotencyKey` model with a unique constraint on `(key, merchant_id)`. During a payout request, the service attempts `get_or_create` on the key within a transaction. If it already exists, the second request fetches its cached `response_status` and `response_body` rather than executing the payout logic.

**What happens if the first request is in flight when the second arrives?**
The initial request creates the `IdempotencyKey` row with `response_status=None`. If a second request arrives while the first is still processing, the system catches the `IntegrityError` or detects `created=False` and sees that `response_status` is `None`. It immediately rejects the second request (e.g., throwing a `Concurrent request in flight` exception) to prevent a race. Only successful or solidly failed requests update the `response_status` and allow valid idempotent returns.

## 4. The State Machine
**Where in the code is failed-to-completed blocked? Show the check.**
Located in the `clean()` method of the `Payout` model:
```python
invalid_transitions = [
    (PayoutStatus.COMPLETED, PayoutStatus.PENDING),
    (PayoutStatus.COMPLETED, PayoutStatus.PROCESSING),
    (PayoutStatus.COMPLETED, PayoutStatus.FAILED),
    (PayoutStatus.FAILED, PayoutStatus.PENDING),
    (PayoutStatus.FAILED, PayoutStatus.PROCESSING),
    (PayoutStatus.FAILED, PayoutStatus.COMPLETED),  # Directly blocks failed to completed
]
if (old_status, self.status) in invalid_transitions:
    raise ValidationError(f"Invalid state transition from {old_status} to {self.status}")
```
By placing this in `clean()` and forcing `self.full_clean()` during `save()`, any explicit or background worker transition (like an out-of-order retry trying to override a failure) will raise an error.

## 5. The AI Audit
**One specific example where AI wrote subtly wrong code (bad locking, wrong aggregation, race condition). Paste what it gave you, what you caught, and what you replaced it with.**
*What it gave me:* For idempotency, the LLM initially suggested using Redis with `cache.set(key, "processing", timeout=86400)`. 
*What I caught:* Using an external Redis cache for idempotency in a financial app creates a race condition known as the "two-generals problem". If Redis goes down or eviction kicks in early, duplicate requests will pass. Moreover, if the API instance crashes after the Payout commits to PostgreSQL but *before* caching the successful response to Redis, the next request will think it's a new payout and charge the user twice.
*What I replaced it with:* I used PostgreSQL as the single source of truth for both idempotency keys and ledger data via the `IdempotencyKey` model, wrapped within the same `transaction.atomic()` block.
