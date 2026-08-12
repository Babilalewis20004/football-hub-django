from django.db.models import Count, Q

from blog.models import Post, Category


def get_homepage_context():
    published = Post.objects.filter(is_published=True).select_related("author", "category")

    hero_post = published.order_by("-created_at").first()
    exclude_ids = [hero_post.id] if hero_post else []

    hero_side_posts = list(
        published.exclude(id__in=exclude_ids).order_by("-created_at")[:2]
    )
    exclude_ids += [post.id for post in hero_side_posts]

    editors_picks = list(
        published.exclude(id__in=exclude_ids).order_by("-views")[:3]
    )
    exclude_ids += [post.id for post in editors_picks]

    latest_posts = list(
        published.exclude(id__in=exclude_ids).order_by("-created_at")[:6]
    )

    categories = Category.objects.annotate(
        post_count=Count("posts", filter=Q(posts__is_published=True))
    ).order_by("-post_count")

    return {
        "hero_post": hero_post,
        "hero_side_posts": hero_side_posts,
        "editors_picks": editors_picks,
        "latest_posts": latest_posts,
        "categories": categories,
    }
