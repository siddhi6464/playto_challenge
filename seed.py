import os
import django
from datetime import timedelta
from django.utils import timezone

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'playto_payouts.settings')
django.setup()

from core.models import Merchant, LedgerEntry

def seed_data():
    print("Clearing existing data...")
    Merchant.objects.all().delete()
    
    print("Seeding Merchants...")
    m1 = Merchant.objects.create(name="Acme Corp (India)")
    m2 = Merchant.objects.create(name="Globex Tech")
    
    print("Seeding Ledger Entries for balances...")
    # Acme has 5000 USD equivalent in INR paise (e.g. 100,000 INR = 10,000,000 paise)
    LedgerEntry.objects.create(
        merchant=m1,
        entry_type=LedgerEntry.EntryType.CREDIT,
        amount_paise=10000000,
        description="Initial deposit from Stripe"
    )
    LedgerEntry.objects.create(
        merchant=m1,
        entry_type=LedgerEntry.EntryType.DEBIT,
        amount_paise=2000000,
        description="Payout to HDFC Bank"
    )
    # Available balance for m1 = 80,000 INR = 8,000,000 paise
    
    # Globex has 500 INR
    LedgerEntry.objects.create(
        merchant=m2,
        entry_type=LedgerEntry.EntryType.CREDIT,
        amount_paise=50000,
        description="Test transaction"
    )
    
    print("Seeding complete.")
    print(f"Merchant 1 ID: {m1.id} (Balance: 8,000,000 paise)")
    print(f"Merchant 2 ID: {m2.id} (Balance: 50,000 paise)")

if __name__ == "__main__":
    seed_data()
