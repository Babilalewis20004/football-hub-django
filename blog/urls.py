from django.urls import path

from blog.views.home import home
from blog.views.posts import (
    post_detail,
    post_create,
    post_update,
    post_delete,
    post_publish,
    post_approve,
    post_request_changes,
    post_submit_for_review,
    post_withdraw_from_review,
    editor_dashboard,
    author_dashboard,
    editor_dashboard_partial,
    author_dashboard_partial,
)

from blog.views.search import search_posts
from blog.views.interactions import like_post, bookmark_post
from blog.views.taxonomy import (
    author_posts,
    category_posts,
    tag_posts,
)
from blog.views.dashboard import (
    dashboard,
    saved_posts,
)


urlpatterns = [
    # Public
    path('', home, name='home'),

    # CRUD (specific first)
    path('post/create/', post_create, name='post_create'),
    path('post/<slug:slug>/edit/', post_update, name='post_update'),
    path('post/<slug:slug>/delete/', post_delete, name='post_delete'),
    path("post/<slug:slug>/publish/", post_publish, name="post_publish"),
    path("post/<slug:slug>/approve/", post_approve, name="post_approve"),
    path("post/<slug:slug>/request-changes/", post_request_changes, name="post_request_changes"),
    path("post/<slug:slug>/submit-review/", post_submit_for_review, name="post_submit_for_review"),
    path("post/<slug:slug>/withdraw/", post_withdraw_from_review, name="post_withdraw_from_review"),

    # Dynamic last
    path('post/<slug:slug>/', post_detail, name='post_detail'),

    # Search
    path('search/', search_posts, name='search'),

    # Interactions
    path('like/<slug:slug>/', like_post, name='like_post'),
    path('bookmark/<slug:slug>/', bookmark_post, name='bookmark_post'),

    # Filters
    path('author/<str:username>/', author_posts, name='author_posts'),
    path('category/<slug:slug>/', category_posts, name='category_posts'),
    path('tag/<slug:slug>/', tag_posts, name='tag_posts'),

    # Dashboard
    path('dashboard/', dashboard, name='dashboard'),
    path('saved/', saved_posts, name='saved_posts'),
    path("dashboard/editor/", editor_dashboard, name="editor_dashboard"),
    path("dashboard/author/", author_dashboard, name="author_dashboard"),
    path("dashboard/editor/partial/", editor_dashboard_partial, name="editor_dashboard_partial"),
    path("dashboard/author/partial/", author_dashboard_partial, name="author_dashboard_partial"),
]
