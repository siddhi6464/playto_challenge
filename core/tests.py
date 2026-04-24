import threading
import uuid
from django.test import TestCase, TransactionTestCase
from django.db import transaction, connection
from django.urls import reverse
from rest_framework.test import APIClient
from .models import Merchant, LedgerEntry, IdempotencyKey

class ConcurrencyTest(TransactionTestCase):
    # Using TransactionTestCase since we test transaction blocking/concurrency over DB connections
    def setUp(self):
        self.merchant = Merchant.objects.create(name="Test Merchant")
        LedgerEntry.objects.create(
            merchant=self.merchant,
            entry_type=LedgerEntry.EntryType.CREDIT,
            amount_paise=10000,
            description="Initial deposit"
        )
        self.client = APIClient()
        self.url = '/api/v1/payouts/'
        
    def test_concurrent_overdraw(self):
        # The merchant has 10,000 paise. Two payout requests for 6,000 paise concurrently.
        # Only one should succeed.
        
        payload1 = {
            'merchant_id': self.merchant.id,
            'amount_paise': 6000,
            'bank_account_id': 'bank_1'
        }
        
        payload2 = {
            'merchant_id': self.merchant.id,
            'amount_paise': 6000,
            'bank_account_id': 'bank_2'
        }

        results = []
        
        def worker(payload, idempotency_key):
            # Each thread needs its own db connection so it doesn't share transactions
            connection.close()  
            client = APIClient()
            response = client.post(self.url, payload, headers={'Idempotency-Key': idempotency_key}, format='json')
            results.append(response.status_code)
            connection.close()
            
        t1 = threading.Thread(target=worker, args=(payload1, str(uuid.uuid4())))
        t2 = threading.Thread(target=worker, args=(payload2, str(uuid.uuid4())))
        
        t1.start()
        t2.start()
        
        t1.join()
        t2.join()
        
        # Expecting one 201 Created and one 400 Bad Request (Insufficient balance)
        self.assertIn(201, results)
        self.assertIn(400, results)

class IdempotencyTest(TestCase):
    def setUp(self):
        self.merchant = Merchant.objects.create(name="Test Merchant")
        LedgerEntry.objects.create(
            merchant=self.merchant,
            entry_type=LedgerEntry.EntryType.CREDIT,
            amount_paise=50000,
            description="Initial deposit"
        )
        self.client = APIClient()
        self.url = '/api/v1/payouts/'
        
    def test_exact_same_response(self):
        idem_key = str(uuid.uuid4())
        payload = {
            'merchant_id': self.merchant.id,
            'amount_paise': 1000,
            'bank_account_id': 'bank_123'
        }
        
        resp1 = self.client.post(self.url, payload, headers={'Idempotency-Key': idem_key}, format='json')
        resp2 = self.client.post(self.url, payload, headers={'Idempotency-Key': idem_key}, format='json')
        
        self.assertEqual(resp1.status_code, 201)
        self.assertEqual(resp2.status_code, 201)
        self.assertEqual(resp1.data, resp2.data)
        
        # Ensure only 1 payout and 1 debit was created
        self.assertEqual(self.merchant.payouts.count(), 1)
        debits = LedgerEntry.objects.filter(merchant=self.merchant, entry_type=LedgerEntry.EntryType.DEBIT)
        self.assertEqual(debits.count(), 1)
