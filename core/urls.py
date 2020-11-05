from django.urls import path,re_path
from core import views

app_name = 'core'

urlpatterns = [
    path('', views.HomeView.as_view(),name='home'),
    path('product/<slug>', views.ItemDetailView.as_view(),name='product'),
    path('order-summary', views.OrderSummaryView.as_view(),name='order-summary'),
    path('checkout/', views.CheckoutView.as_view(),name='checkout'),
    path('payment/<payment_option>', views.PaymentView.as_view(),name='payment'),
    path('add-coupon/', views.AddCouponView.as_view(), name='add-coupon'),
    path('add-to-cart/<slug>/', views.add_to_cart, name='add-to-cart'),
    path('remove-from-cart/<slug>/', views.remove_from_cart, name='remove-from-cart'),
    path('remove-single-item-from-cart/<slug>/', views.remove_single_item_from_cart, name='remove-single-item-from-cart'),
    path('request-refund', views.RequestRefundView.as_view(), name='request-refund'),
    path('stripe/', views.StripeView.as_view(), name='stripe'),
]
