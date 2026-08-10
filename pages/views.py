from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.generic import TemplateView

from .forms import FeedbackForm


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
