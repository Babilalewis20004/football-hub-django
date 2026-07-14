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