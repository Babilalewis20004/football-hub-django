"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
######second
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from django.contrib.sitemaps.views import sitemap

from users import views as user_views
from config.views import csp_report_view, robots_txt
from blog.sitemaps import PostSitemap, CategorySitemap, StaticViewSitemap

sitemaps = {
    "posts": PostSitemap,
    "categories": CategorySitemap,
    "static": StaticViewSitemap,
}

urlpatterns = [
    path('admin/', admin.site.urls),

    path('csp-report/', csp_report_view, name='csp_report'),

    path(
        'sitemap.xml',
        sitemap,
        {'sitemaps': sitemaps},
        name='sitemap',
    ),
    path('robots.txt', robots_txt, name='robots_txt'),

    path('', include('blog.urls')),
    path('users/', include('users.urls')),
    path('chat/', include('chat.urls')),
    path('captcha/', include('captcha.urls')),
    path('', include('pages.urls')),

    path('login/', user_views.login_view, name='login'),
    path('logout/', user_views.logout_view, name='logout'),

    path(
        'password-reset/',
        auth_views.PasswordResetView.as_view(
            template_name='users/password_reset_form.html',
            email_template_name='users/password_reset_email.html',
            subject_template_name='users/password_reset_subject.txt',
            success_url='/password-reset/done/',
        ),
        name='password_reset',
    ),
    path(
        'password-reset/done/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='users/password_reset_done.html',
        ),
        name='password_reset_done',
    ),
    path(
        'password-reset/confirm/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='users/password_reset_confirm.html',
            success_url='/password-reset/complete/',
        ),
        name='password_reset_confirm',
    ),
    path(
        'password-reset/complete/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='users/password_reset_complete.html',
        ),
        name='password_reset_complete',
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
