from django.shortcuts import render
from django.contrib.auth.decorators import login_required
import logging

logger = logging.getLogger("blog")

from blog.models import Post, Bookmark


@login_required
def dashboard(request):
    logger.info(f"Dashboard accessed by {request.user.username}")

    user_posts = Post.objects.filter(author=request.user)
    bookmarks = Bookmark.objects.filter(user=request.user)

    logger.info(
        f"Dashboard stats for {request.user.username}: "
        f"{user_posts.count()} posts, {bookmarks.count()} bookmarks"
    )

    return render(
        request,
        "blog/dashboard.html",
        {
            "user_posts": user_posts,
            "bookmarks": bookmarks,
            "post_count": user_posts.count(),
            "bookmark_count": bookmarks.count(),
        }
    )


@login_required
def saved_posts(request):
    logger.info(f"Saved posts viewed by {request.user.username}")

    bookmarks = Bookmark.objects.filter(user=request.user)

    logger.info(
        f"{request.user.username} has {bookmarks.count()} saved posts"
    )

    return render(
        request,
        "blog/saved_posts.html",
        {
            "bookmarks": bookmarks,
        }
    )
