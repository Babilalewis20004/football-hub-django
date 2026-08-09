from django.shortcuts import render
from blog.services.homepage import get_homepage_context
from blog.models import Post
import logging

logger = logging.getLogger("blog")
security_logger = logging.getLogger("security")


def home(request):
    posts = Post.objects.filter(status="published").order_by("-created_at")
    user = request.user.username if request.user.is_authenticated else "Anonymous"
    logger.info(f"Homepage accessed by {user}")

    # security logging
    if any(
        bad in value.lower()
        for value in request.GET.values()
        for bad in ["sql", "drop", "union"]
    ):
        security_logger.warning(f"Suspicious homepage query: {request.GET}")


    context = get_homepage_context()
    context["posts"] = posts
    logger.info("Homepage context generated")

    return render(request, "blog/home.html", context)
