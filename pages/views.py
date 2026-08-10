from django.views.generic import TemplateView


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
