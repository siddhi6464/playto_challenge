from django.urls import path
from .views import MerchantBalanceView, PayoutListCreateView

urlpatterns = [
    path('merchants/<int:pk>/balance/', MerchantBalanceView.as_view(), name='merchant-balance'),
    path('payouts/', PayoutListCreateView.as_view(), name='payout-list-create'),
]
