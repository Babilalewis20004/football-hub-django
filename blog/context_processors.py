# blog/context_processors.py

from .models import Category, Post


def sidebar_data(request):
    return {
        'sidebar_categories': Category.objects.all(),
        'sidebar_trending_posts': Post.objects.filter(
            is_published=True
        ).order_by('-views')[:5],
        'sidebar_latest_posts': Post.objects.filter(
            is_published=True
        ).order_by('-created_at')[:5],
    }


def seo_defaults(request):
    """
    Site-wide SEO context: a canonical URL (path only, no query string,
    so paginated/filtered views all canonicalize to the same page) and
    the site name used in <title> suffixes and OG/Twitter tags.
    """
    return {
        'canonical_url': request.build_absolute_uri(request.path),
        'site_name': 'Football Hub',
    }