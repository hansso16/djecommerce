from django.conf import settings
from django.core import serializers
from django.http import JsonResponse
from django.shortcuts import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView, View
from core import models
from django.utils import timezone
from .forms import CheckoutForm, CouponForm, RefundForm, PaymentForm
import random
import string
import stripe
from django.conf import settings
# from core.mixins import mixins

stripe.api_key = settings.STRIPE_SECRET_KEY
STRIPE_PUBLIC_KEY = settings.STRIPE_PUBLIC_KEY


# Create your views here.
def create_ref_code():
    return ''.join(random.choices(string.ascii_lowercase+string.digits, k=20))


def product(request):
    return render(request, "product.html")


def is_valid_form(values):
    valid = True
    for field in values:
        if field == '':
            valid = False
    return valid


class CheckoutView(View):
    def get(self, *args, **kwargs):
        try:
            form = CheckoutForm()
            order = models.Order.objects.get(
                user=self.request.user, is_ordered=False)
            context = {
                'form': form,
                'order': order,
                'couponform': CouponForm(),
                'DISPLAY_COUPON_FORM': True
            }

            shipping_address_qs = models.Address.objects.filter(
                user=self.request.user, address_type='S', default=True)
            if shipping_address_qs.exists():
                context.update(
                    {'default_shipping_address': shipping_address_qs[0]})

            billing_address_qs = models.Address.objects.filter(
                user=self.request.user, address_type='B', default=True)
            if shipping_address_qs.exists():
                context.update(
                    {'default_billing_address': billing_address_qs[0]})

            return render(self.request, "checkout.html", context)
        except ObjectDoesNotExist:
            messages.warning(self.request, "You do not have an active order")
            return redirect("core:checkout")

    def post(self, *args, **kwargs):
        form = CheckoutForm(self.request.POST or None)
        try:
            order = models.Order.objects.get(
                user=self.request.user, is_ordered=False)
            if form.is_valid():

                use_default_shipping = form.cleaned_data.get(
                    'use_default_shipping')

                if use_default_shipping:
                    print("Using the default shipping address")
                    address_qs = models.Address.objects.filter(
                        user=self.request.user, address_type='S', default=True)
                    if address_qs.exists():
                        shipping_address = address_qs[0]
                        order.shipping_address = shipping_address
                        order.save()
                    else:
                        messages.warning(
                            self.request, "No default shipping address available")
                        return redirect('core:checkout')
                else:
                    print("User is entering a new shipping address")
                    shipping_address1 = form.cleaned_data.get(
                        'shipping_address')
                    shipping_address2 = form.cleaned_data.get(
                        'shipping_address2')
                    shipping_country = form.cleaned_data.get(
                        'shipping_country')
                    shipping_zip = form.cleaned_data.get('shipping_zip')
                    if is_valid_form([shipping_address1, shipping_country, shipping_zip]):
                        shipping_address = models.Address(
                            user=self.request.user,
                            street_address=shipping_address1,
                            apartment_address=shipping_address2,
                            country=shipping_country,
                            zip=shipping_zip,
                            address_type='S',
                        )
                        shipping_address.save()
                        order.shipping_address = shipping_address
                        order.save()

                        set_default_shipping = form.cleaned_data.get(
                            'set_default_shipping')
                        if set_default_shipping:
                            shipping_address.default = True
                            shipping_address.save()
                    else:
                        messages.warning(
                            sef.request, "Please fill inthe required shipping address fields")

                use_default_billing = form.cleaned_data.get(
                    'use_default_billing')
                same_billing_address = form.cleaned_data.get(
                    'same_billing_address')

                if same_billing_address:
                    billing_address = shipping_address
                    billing_address.pk = None
                    billing_address.save()
                    billing_address.address_type = 'B'
                    billing_address.save()
                    order.billing_address = billing_address
                    order.save()

                elif use_default_billing:
                    print("Using the default BILING address")
                    address_qs = models.Address.objects.filter(
                        user=self.request.user, address_type='B', default=True)
                    if address_qs.exists():
                        billing_address = address_qs[0]
                        order.billing_address = billing_address
                        order.save()
                    else:
                        messages.warning(
                            self.request, "No default billing address available")
                        return redirect('core:checkout')
                else:
                    print("User is entering a new billing address")
                    billing_address1 = form.cleaned_data.get('billing_address')
                    billing_address2 = form.cleaned_data.get(
                        'billing_address2')
                    billing_country = form.cleaned_data.get('billing_country')
                    billing_zip = form.cleaned_data.get('billing_zip')

                    if is_valid_form([billing_address1, billing_country, billing_zip]):

                        billing_address = models.Address(
                            user=self.request.user,
                            street_address=billing_address1,
                            apartment_address=billing_address2,
                            country=billing_country,
                            zip=billing_zip,
                            address_type='B'
                        )
                        billing_address.save()
                        order.billing_address = billing_address
                        order.save()

                        set_default_billing = form.cleaned_data.get(
                            'set_default_billing')
                        if set_default_billing:
                            billing_address.default = True
                            billing_address.save()
                    else:
                        messages.warning(
                            sef.request, "Please fill inthe required billing address fields")

                payment_option = form.cleaned_data.get('payment_option')
                # TODO: add redirect to the selected payment option
                if payment_option == 'S':
                    return redirect('core:payment', payment_option='stripe')
                elif payment_option == 'P':
                    return redirect('core:payment', payment_option='paypal')
                else:
                    messages.warning(self.request, "Invalid Payment Option")
                    return redirect('core:checkout')
            else:
                messages.warning(self.request, "Failed checkout")
                return redirect('core:checkout')
        except ObjectDoesNotExist:
            messages.warning(request, "You do not have an active order")
            return redirect("/")


class PaymentView(View):
    def get(self, *args, **kwargs):
        # order
        order = models.Order.objects.get(
            user=self.request.user, is_ordered=False)
        if order.billing_address:
            # userprofile = self.request.user.userprofile
            # if userprofile.one_click_purchasing:
            #     # fetch the users card list
            #     card = stripe.Customer.list_sources(
            #         userprofile.stripe_customer_id,
            #         limit=3,
            #         object='card',
            #     )
            #     print(card)
            #     card_list = card['data']
            #     if len(card_list) > 0:
            #         # update the context with the default card
            #         context.update({
            #             'card': card_list[0]
            #         })

            amount = int(order.get_total() * 100)
            print(amount)
            print(order.payment_intent)
            if order.payment_intent:
                pi_key = order.payment_intent
                payment_intent = stripe.PaymentIntent.retrieve(pi_key,)
                stripe_amt = payment_intent.amount
                print(stripe_amt)
                if amount != stripe_amt:
                    payment_intent = stripe.PaymentIntent.modify(
                        pi_key,
                        amount=amount,
                    )
            else:
                payment_intent = stripe.PaymentIntent.create(
                    amount=amount,
                    currency="usd",
                    payment_method_types=["card"],
                )
                pi_key = payment_intent.id
                order.payment_intent = pi_key
                order.save()

            print("GET")

            context = {
                'order': order,
                'DISPLAY_COUPON_FORM': False,
                'STRIPE_PUBLIC_KEY': STRIPE_PUBLIC_KEY,
            }
            return render(self.request, "payment.html", context)
        else:
            messages.warning(
                self.request, "You have not added a billing address")
            return redirect("core:checkout")

    def post(self, *args, **kwargs):
        order = models.Order.objects.get(
            user=self.request.user, is_ordered=False)
        amount = int(order.get_total() * 100)  # cents
        form = PaymentForm(self.request.POST)
        # userprofile = models.UserProfile.objects.get(user=self.request.user)
        if form.is_valid():
            payment_method_id = form.cleaned_data.get('payment_method_id')
            payment_intent_id = form.cleaned_data.get('payment_intent_id')
            save = form.cleaned_data.get('save')
            use_default = form.cleaned_data.get('use_default')

            # if save:
            #     if userprofile.stripe_customer_id != '' and userprofile.stripe_customer_id is not None:
            #         print('EXIST')
            #         print(customer)
            #         customer = stripe.Customer.retrieve(userprofile.stripe_customer_id)
            #         # customer.sources.create(source=token)
            #     else:
            #         print('CREATE')
            #         print(customer)
            #         customer = stripe.Customer.create(
            #             email=self.request.user.email,
            #             source=token
            #         )
            #         # customer.sources.create(source=token)
            #         userprofile.stripe_customer_id = customer['id']
            #         userprofile.one_click_purchasing = True
            #         userprofile.save()

            try:

                # if use_default or save:
                # charge the customer because we cannot charge the token more than once
                # `source` is obtained with Stripe.js; see https://stripe.com/docs/payments/accept-a-payment-charges#web-create-token
                # charge = stripe.Charge.create(
                #     amount=amount,
                #     currency="usd",
                #     source=token,
                #     # description="My First Test Charge (created for API docs)",
                # )

                if payment_method_id:
                    pi_key = order.payment_intent
                    if pi_key:
                        payment_intent = stripe.PaymentIntent.confirm(
                            pi_key,
                            payment_method=payment_method_id,
                            # confirmation_method="manual",
                        )
                    else:
                        print("SKIP FOR NOW")
                        # payment_intent = stripe.PaymentIntent.create(
                        #     amount=amount,
                        #     currency="usd",
                        #     payment_method_types=["card"],
                        # )
                elif payment_intent_id:
                    payment_intent = stripe.PaymentIntent.retrieve(
                        payment_intent_id,)
                    # Check if the payment succeeded
                    if 'succeeded' != payment_intent.status:
                        # Try one more time
                        payment_intent = stripe.PaymentIntent.confirm(
                            payment_intent_id)

                if 'succeeded' == payment_intent.status:
                    payment_data = payment_intent.charges.data[0]
                    # create the payment

                    payment = models.Payment()
                    payment.stripe_charge_id = payment_data.id
                    payment.user = self.request.user
                    payment.amount = payment_data.amount_captured / 100
                    payment.save()

                    # assign the payment to the order
                    order_items = order.items.all()
                    order_items.update(is_ordered=True)
                    for item in order_items:
                        item.save()

                    order.is_ordered = True
                    order.payment = payment
                    # assign reference code
                    order.ref_code = create_ref_code()
                    order.save()

                    messages.success(
                        self.request, "Your order was successful!")
                return generate_response(payment_intent)

            except stripe.error.CardError as e:
                # Since it's a decline, stripe.error.CardError will be caught
                # print("CardError")
                # print(e)
                # print('Status is: %s' % e.http_status)
                # print('Code is: %s' % e.code)
                # print('Param is: %s' % e.param)
                # print('Message is: %s' % e.user_message)

                return stripe_error_response(e)

            except stripe.error.RateLimitError as e:
                # Too many requests made to the API too quickly
                # print("RateLimitError")
                # print('Status is: %s' % e.http_status)
                # print('Code is: %s' % e.code)
                # print('Param is: %s' % e.param)
                # print('Message is: %s' % e.user_message)

                return stripe_error_response(e)
            except stripe.error.InvalidRequestError as e:
                # Invalid parameters were supplied to Stripe's API
                # print("InvalidRequestError")
                # print('Status is: %s' % e.http_status)
                # print('Code is: %s' % e.code)
                # print('Param is: %s' % e.param)
                # print('Message is: %s' % e.user_message)

                return stripe_error_response(e)
            except stripe.error.AuthenticationError as e:
                # Authentication with Stripe's API failed
                # (maybe you changed API keys recently)
                # print("AuthenticationError")
                # print('Status is: %s' % e.http_status)
                # print('Code is: %s' % e.code)
                # print('Param is: %s' % e.param)
                # print('Message is: %s' % e.user_message)

                return stripe_error_response(e)
            except stripe.error.APIConnectionError as e:
                # Network communication with Stripe failed
                # print("APIConnectionError")
                # print('Status is: %s' % e.http_status)
                # print('Code is: %s' % e.code)
                # print('Param is: %s' % e.param)
                # print('Message is: %s' % e.user_message)

                return stripe_error_response(e)
            except stripe.error.StripeError as e:
                # Display a very generic error to the user, and maybe send
                # yourself an email
                # print("StripeError")
                # print('Status is: %s' % e.http_status)
                # print('Code is: %s' % e.code)
                # print('Param is: %s' % e.param)
                # print('Message is: %s' % e.user_message)

                return stripe_error_response(e)
            except Exception as e:
                # Something else happened, completely unrelated to Stripe
                # Send email to ourselves
                print(e)
                messages.warning(
                    self.request, "A serious error occurred. We have been notified.")
                return redirect("/")


def stripe_error_response(error):
    data = {
        'error': {
            'status': error.http_status,
            'code': error.code,
            'param': error.param,
            'message': error.user_message
        }
    }
    return JsonResponse(data)


def generate_response(intent):
    if intent.status == 'requires_action' and intent.next_action.type == 'use_stripe_sdk':
        data = {
            'requires_action': True,
            'payment_intent_client_secret': intent.client_secret,
        }
        return JsonResponse(data)
    elif intent.status == 'succeeded':
        # The payment didn’t need any additional actions and completed!
        data = {
            'success': True
        }
        return JsonResponse(data)
    else:
        # Invalid status
        data = {
            'error': 'Invalid PaymentIntent status'
        }
        return JsonResponse(data)


class HomeView(ListView):
    model = models.Item
    paginate_by = 10
    template_name = "home.html"


class ItemDetailView(DetailView):
    context_object_name = 'item'
    model = models.Item
    template_name = 'product.html'


class OrderSummaryView(LoginRequiredMixin, View):
    def get(self, *args, **kwargs):
        try:
            order = models.Order.objects.get(
                user=self.request.user, is_ordered=False)
            context = {
                'object': order
            }
            return render(self.request, 'order_summary.html', context)
        except ObjectDoesNotExist:
            messages.warning(self.request, "You do not have an active order")
            return redirect("/")


@login_required
def add_to_cart(request, slug):
    item = get_object_or_404(models.Item, slug=slug)
    order_item, created = models.OrderItem.objects.get_or_create(
        item=item, user=request.user, is_ordered=False)
    order_qs = models.Order.objects.filter(user=request.user, is_ordered=False)

    if order_qs.exists():
        order = order_qs[0]
        # check if the order item is in the order
        if order.items.filter(item__slug=item.slug).exists():
            order_item.quantity += 1
            order_item.save()
            messages.info(request, "The item quantity was updated.")
            return redirect('core:order-summary')
        else:
            order.items.add(order_item)
            messages.info(request, "This item was added to your cart.")
            return redirect('core:order-summary')
    else:
        ordered_date = timezone.now()
        order = models.Order.objects.create(
            user=request.user, ordered_date=ordered_date)
        order.items.add(order_item)
        messages.info(request, "This item was added to your cart.")
        return redirect('core:order-summary')


@login_required
def remove_from_cart(request, slug):
    item = get_object_or_404(models.Item, slug=slug)

    order_qs = models.Order.objects.filter(user=request.user, is_ordered=False)

    if order_qs.exists():
        order = order_qs[0]
        # check if the order item is in the order
        if order.items.filter(item__slug=item.slug).exists():
            order_item = models.OrderItem.objects.get_or_create(
                item=item, user=request.user, is_ordered=False)[0]
            order.items.remove(order_item)
            order_item.delete()
            messages.info(request, "This item was removed from your cart")
            return redirect('core:order-summary')
        else:
            messages.info(request, "This item was not in your cart")
            return redirect('core:product', slug=slug)
    else:
        messages.info(request, "You do not have an active order")
        return redirect('core:product', slug=slug)


@login_required
def remove_single_item_from_cart(request, slug):
    item = get_object_or_404(models.Item, slug=slug)

    order_qs = models.Order.objects.filter(user=request.user, is_ordered=False)

    if order_qs.exists():
        order = order_qs[0]
        # check if the order item is in the order
        if order.items.filter(item__slug=item.slug).exists():
            order_item = models.OrderItem.objects.get_or_create(
                item=item, user=request.user, is_ordered=False)[0]
            order_item.quantity -= 1
            if order_item.quantity == 0:
                order.items.remove(order_item)
                messages.info(
                    request, "The item " + order_item.item.title + " was removed from your cart.")
                return redirect('core:order-summary')
            else:
                order_item.save()
                messages.info(request, "The item quantity was updated.")
                return redirect('core:order-summary')
        else:
            messages.info(request, "This item was not in your cart")
            return redirect('core:product', slug=slug)
    else:
        messages.info(request, "You do not have an active order")
        return redirect('core:home')


def get_coupon(request, code):
    try:
        coupon = models.Coupon.objects.get(code=code)
        return coupon
    except ObjectDoesNotExist:
        messages.warning(request, "This coupon does not exist")
        return None


class AddCouponView(View):
    def post(self, *args, **kwargs):
        form = CouponForm(self.request.POST or None)
        if form.is_valid():
            try:
                code = form.cleaned_data.get('code')
                order = models.Order.objects.get(
                    user=self.request.user, is_ordered=False)
                if order.coupon is not None:
                    coupon_exists = True

                coupon = get_coupon(self.request, code)
                if coupon:
                    order.coupon = coupon
                    order.save()
                    if coupon_exists:
                        messages.info(self.request, "Coupon is now updated.")
                    else:
                        messages.info(
                            self.request, "The coupon is now applied to the order.")

                return redirect("core:checkout")

            except ObjectDoesNotExist:
                messages.warning(
                    self.request, "You do not have an active order")
                return redirect("core:checkout")


class RequestRefundView(View):
    def get(self, *args, **kwargs):
        form = RefundForm()
        context = {
            'form': form
        }
        return render(self.request, "request_refund.html", context)

    def post(self, *args, **kwargs):
        form = RefundForm(self.request.POST)
        if form.is_valid():
            ref_code = form.cleaned_data.get('ref_code')
            message = form.cleaned_data.get('message')
            email = form.cleaned_data.get('email')
            # Edit the order
            try:
                order = models.Order.objects.get(ref_code=ref_code)
                order.refund_requested = True
                order.save()

                refund = models.Refund()
                refund.order = order
                refund.reason = message
                refund.email = email
                refund.save()
                messages.info(self.request, "Your request was received.")
                return redirect("core:request-refund")
            except ObjectDoesNotExist:
                messages.warning(self.request, "This order does not exist.")
                return redirect("core:request-refund")


class CreateSessionView(View):
    def post(self, *args, **kwargs):
        try:
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[
                    {
                        'price_data': {
                            'currency': 'usd',
                            'unit_amount': 2000,
                            'product_data': {
                                'name': 'Stubborn Attachments',
                                'images': ['https://i.imgur.com/EHyR2nP.png'],
                            },
                        },
                        'quantity': 1,
                    },
                ],
                mode='payment',
                success_url=YOUR_DOMAIN + '/success.html',
                cancel_url=YOUR_DOMAIN + '/cancel.html',
            )
            return jsonify({'id': checkout_session.id})
        except Exception as e:
            return jsonify(error=str(e)), 403
    context_object_name = 'item'
    model = models.Item
    template_name = 'product.html'


class StripeView(View):
    def get(self, *args, **kwargs):
        return render(self.request, "stripe.html")

    def post(self, *args, **kwargs):
        print('POST')
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': 'T-shirt',

                    },
                    'unit_amount': 2000,  # cents
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=self.request.build_absolute_uri(reverse('core:home')),
            cancel_url=self.request.build_absolute_uri(reverse('core:home')),
        )
        context = {
            'session_id': session.id,
            'public_key': 'pk_test_51HjHazBfXNIOP49r1WE9tONnHGGQa2U8lNQZsVBCXDdEa0DAoTlE7lVWKSDe4Dz68n9ogUM96gGEcXk2kakxx4vu00kc2huSdL',
        }
        print(context)
        return JsonResponse(context)
