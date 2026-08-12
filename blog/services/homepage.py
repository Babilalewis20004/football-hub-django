from blog.models import Post, Category


def get_homepage_context():
    published = Post.objects.filter(is_published=True)

    hero_post = published.order_by("-created_at").first()

    popular_posts = published.order_by("-views")[:5]
    latest_posts = published.order_by("-created_at")[1:]
    worldcup_posts = published.filter(
        category__name__icontains="world cup"
    )[:6]

    bullet_links = [
        {"title": "2026 FIFA World Cup match schedule", "url": "#"},
        {"title": "FIFA World Cup Bracket 2026", "url": "#"},
        {"title": "8 most important players of the quarterfinals", "url": "#"},
        {"title": "Yellow card watch: WC QFs", "url": "#"},
    ]

    categories = Category.objects.all()

    return {
        "hero_post": hero_post,
        "latest_posts": latest_posts,
        "popular_posts": popular_posts,
        "slider_posts": popular_posts,
        "worldcup_posts": worldcup_posts,
        "bullet_links": bullet_links,
        "categories": categories,
    }
