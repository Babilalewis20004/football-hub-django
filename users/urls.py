from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register, name='register'),
    path('profile/', views.profile, name='profile'),
    path('profile/delete/', views.delete_account, name='delete_account'),

    path('2fa/setup/', views.two_factor_setup, name='two_factor_setup'),
    path('2fa/verify/', views.two_factor_verify, name='two_factor_verify'),
    path('2fa/disable/', views.two_factor_disable, name='two_factor_disable'),
    path(
        '2fa/recovery-codes/regenerate/',
        views.two_factor_regenerate_codes,
        name='two_factor_regenerate_codes',
    ),
]
