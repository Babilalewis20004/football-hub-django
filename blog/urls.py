from django.urls import path
from django.contrib.auth.views import LogoutView

from . import views


urlpatterns = [
    # -------------------------
    # Public Pages
    # -------------------------
    path('', views.home, name='home'),

    # Post Detail
    path('post/<slug:slug>/', views.post_detail, name='post_detail'),

    # -------------------------
    # CRUD Operations (Required by Tests)
    # -------------------------
    path('post/create/', views.post_create, name='post_create'),
    path('post/<slug:slug>/edit/', views.post_update, name='post_update'),
    path('post/<slug:slug>/delete/', views.post_delete, name='post_delete'),

    # -------------------------
    # Search (Tests expect name="search")
    # -------------------------
    path('search/', views.search_posts, name='search'),

    # -------------------------
    # Interactions
    # -------------------------
    path('like/<slug:slug>/', views.like_post, name='like_post'),
    path('bookmark/<slug:slug>/', views.bookmark_post, name='bookmark_post'),

    # -------------------------
    # Filters
    # -------------------------
    path('author/<str:username>/', views.author_posts, name='author_posts'),
    path('category/<slug:slug>/', views.category_posts, name='category_posts'),
    path('tag/<slug:slug>/', views.tag_posts, name='tag_posts'),

    # -------------------------
    # User Dashboard
    # -------------------------
    path('dashboard/', views.dashboard, name='dashboard'),
    path('saved/', views.saved_posts, name='saved_posts'),

    # -------------------------
    # Authentication
    # -------------------------
    path(
    "logout/",
    LogoutView.as_view(next_page="home"),
    name="logout"
)
]
