from blog.models import Post


def can_view_post(user, post):
    if post.is_published:
        return True

    return user.is_authenticated and (
        user == post.author or user.has_perm("blog.change_post")
    )


def get_related_posts(post):
    tag_ids = post.tags.values_list("id", flat=True)
    published = Post.objects.filter(is_published=True)

    related_by_tags = published.filter(
        tags__in=tag_ids
    ).exclude(id=post.id)

    related_by_category = published.filter(
        category=post.category
    ).exclude(id=post.id)

    return (related_by_tags | related_by_category).distinct()[:4]
