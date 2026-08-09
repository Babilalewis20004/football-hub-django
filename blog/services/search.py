from django.db.models import Q
from blog.models import Post


def search_posts_queryset(query):
    if not query:
        return Post.objects.none()

    return Post.objects.filter(
        Q(title__icontains=query) |
        Q(content__icontains=query) |
        Q(category__name__icontains=query) |
        Q(tags__name__icontains=query),
        is_published=True,
    ).distinct()
