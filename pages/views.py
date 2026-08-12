from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView

from .forms import FeedbackForm, SubscribeForm
from .models import Subscriber


class PrivacyPolicyView(TemplateView):
    template_name = 'pages/privacy_policy.html'


class TermsOfUseView(TemplateView):
    template_name = 'pages/terms_of_use.html'


class AboutUsView(TemplateView):
    template_name = 'pages/about_us.html'


class CookiesView(TemplateView):
    template_name = 'pages/cookies.html'


class CareersView(TemplateView):
    template_name = 'pages/careers.html'


class ContactUsView(TemplateView):
    template_name = 'pages/contact_us.html'


def feedback_view(request):
    if request.method == 'POST':
        form = FeedbackForm(request.POST)
        if form.is_valid():
            feedback = form.save(commit=False)
            if request.user.is_authenticated:
                feedback.user = request.user
                feedback.name = feedback.name or request.user.get_full_name() or request.user.get_username()
                feedback.email = feedback.email or request.user.email
            feedback.save()
            messages.success(request, "Thanks for your feedback! We appreciate you taking the time to help us improve.")
            return redirect('feedback')
    else:
        form = FeedbackForm()

    return render(request, 'pages/feedback.html', {'form': form})


@require_POST
def subscribe_view(request):
    form = SubscribeForm(request.POST)

    if form.is_valid():
        _, created = Subscriber.objects.get_or_create(email=form.cleaned_data['email'])
        if created:
            messages.success(request, "You're subscribed! Thanks for joining the Football Hub newsletter.")
        else:
            messages.info(request, "You're already subscribed with that email.")
    else:
        messages.error(request, "Please enter a valid email address.")

    next_url = request.POST.get('next')
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect(next_url)
    return redirect('home')
