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

    is_bookmarked = Bookmark.objects.filter(user=request.user, post=post).exists()

    # Re-render the whole engagement block (like/comment/share/bookmark icons
    # + the likes/views count line) so the count stays in sync with the icon
    # state in a single HTMX swap, instead of drifting out of sync with a
    # narrower partial that only covered the button itself.
    html = render_to_string(
        "partials/post_engagement.html",
        {"post": post, "user": request.user, "is_bookmarked": is_bookmarked},
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
        "partials/post_engagement.html",
        {"post": post, "user": request.user, "is_bookmarked": created},
        request=request,
    )

    return HttpResponse(html)
