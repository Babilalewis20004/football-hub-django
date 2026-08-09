from django.shortcuts import render
from django.db.models import Q
from django.core.paginator import Paginator
import logging

logger = logging.getLogger("blog")
security_logger = logging.getLogger("security")

from blog.models import Post


def search_posts(request):
    query = request.GET.get("q", "").strip()
    results = Post.objects.none()

    # Log the search query
    if query:
        logger.info(f"Search performed by {request.user.username if request.user.is_authenticated else 'Anonymous'}: '{query}'")

        # Optional: security logging for suspicious queries
        if any(term in query.lower() for term in ["drop", "delete", "union", "sql", "--", ";"]):
            security_logger.warning(f"Suspicious search query detected: '{query}' from IP {request.META.get('REMOTE_ADDR')}")

        results = Post.objects.filter(
            Q(title__icontains=query) |
            Q(content__icontains=query) |
            Q(category__name__icontains=query) |
            Q(tags__name__icontains=query),
            is_published=True,
        ).distinct()

        logger.info(f"Search results count for '{query}': {results.count()}")

    else:
        logger.info(f"Empty search submitted by {request.user.username if request.user.is_authenticated else 'Anonymous'}")

    paginator = Paginator(results, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "blog/search_results.html",
        {
            "results": page_obj,
            "query": query,
        }
    )
