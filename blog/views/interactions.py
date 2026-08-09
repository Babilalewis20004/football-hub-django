from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.template.loader import render_to_string
import logging

logger = logging.getLogger("blog")

from blog.models import Post, Bookmark
from blog.services.posts import can_view_post


@require_POST
@login_required
def like_post(request, slug):
    post = get_object_or_404(Post, slug=slug)

    if not can_view_post(request.user, post):
        return HttpResponseForbidden("This post is not published yet.")

    # Toggle like
    if request.user in post.likes.all():
        post.likes.remove(request.user)
        logger.info(f"{request.user.username} unliked post: {post.slug}")
    else:
        post.likes.add(request.user)
        logger.info(f"{request.user.username} liked post: {post.slug}")

    # Render ONLY the like section partial
    html = render_to_string(
        "partials/like_button.html",
        {"post": post, "user": request.user},
        request=request,
    )

    return HttpResponse(html)

@require_POST
@login_required
def bookmark_post(request, slug):
    post = get_object_or_404(Post, slug=slug)

    if not can_view_post(request.user, post):
        return HttpResponseForbidden("This post is not published yet.")

    bookmark, created = Bookmark.objects.get_or_create(user=request.user, post=post)
    if created:
        logger.info(f"{request.user.username} bookmarked post: {post.slug}")
    else:
        bookmark.delete()
        logger.info(f"{request.user.username} removed bookmark from post: {post.slug}")

    html = render_to_string(
        "partials/bookmark_button.html",
        {
            "post": post,
            "user": request.user,
            "is_bookmarked": created,
            "bookmark_count": post.bookmarked_by.count(),
        },
        request=request,
    )

    return HttpResponse(html)
