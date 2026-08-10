from django.urls import path

from pages.views import (
    PrivacyPolicyView,
    TermsOfUseView,
    AboutUsView,
    CookiesView,
    CareersView,
    ContactUsView,
)

urlpatterns = [
    path('privacy-policy/', PrivacyPolicyView.as_view(), name='privacy_policy'),
    path('terms-of-use/', TermsOfUseView.as_view(), name='terms_of_use'),
    path('about-us/', AboutUsView.as_view(), name='about_us'),
    path('cookies/', CookiesView.as_view(), name='cookies'),
    path('careers/', CareersView.as_view(), name='careers'),
    path('contact-us/', ContactUsView.as_view(), name='contact_us'),
]
