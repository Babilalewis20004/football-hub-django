from django.shortcuts import render, get_object_or_404
from django.contrib.auth import get_user_model
from taggit.models import Tag
import logging

logger = logging.getLogger("blog")
security_logger = logging.getLogger("security")

from blog.models import Post, Category

User = get_user_model()


def author_posts(request, username):
    author = get_object_or_404(User, username=username)
    posts = Post.objects.filter(author=author, is_published=True)

    logger.info(
        f"Author posts viewed: author={author.username}, "
        f"viewer={request.user.username if request.user.is_authenticated else 'Anonymous'}, "
        f"count={posts.count()}"
    )

    return render(
        request,
        "blog/author_posts.html",
        {
            "author": author,
            "posts": posts,
        }
    )


def category_posts(request, slug):
    category = get_object_or_404(Category, slug=slug)
    posts = Post.objects.filter(category=category, is_published=True)

    logger.info(
        f"Category posts viewed: category={category.name}, "
        f"viewer={request.user.username if request.user.is_authenticated else 'Anonymous'}, "
        f"count={posts.count()}"
    )

    return render(
        request,
        "blog/category_posts.html",
        {
            "category": category,
            "posts": posts,
        }
    )


def tag_posts(request, slug):
    tag = get_object_or_404(Tag, slug=slug)
    posts = Post.objects.filter(tags__in=[tag], is_published=True)

    logger.info(
        f"Tag posts viewed: tag={tag.name}, "
        f"viewer={request.user.username if request.user.is_authenticated else 'Anonymous'}, "
        f"count={posts.count()}"
    )

    return render(
        request,
        "blog/tag_posts.html",
        {
            "tag": tag,
            "posts": posts,
        }
    )
