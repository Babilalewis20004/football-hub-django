#from django.shortcuts import render
from django.shortcuts import render
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect

from django.contrib.auth.decorators import login_required
from django.template.loader import render_to_string
from django.contrib.auth import get_user_model

from django.core.paginator import Paginator
from django.db.models import Q

from .models import Post, Bookmark
from .models import Category

from .forms import PostForm
from .forms import CommentForm
from taggit.models import Tag

User = get_user_model()


def home(request):

    # HERO ARTICLE (latest post)
    hero_post = Post.objects.order_by('-created_at').first()

    # POPULAR POSTS (sidebar + slider)
    popular_posts = Post.objects.order_by('-views')[:5]
    slider_posts = popular_posts

    # LATEST POSTS (main feed)
    latest_posts = Post.objects.order_by('-created_at')[1:]

    # WORLD CUP POSTS (article grid)
    worldcup_posts = Post.objects.filter(
        category__name__icontains="world cup"
    )[:6]

    # BULLET LINKS (you can replace with your own model later)
    bullet_links = [
        {"title": "2026 FIFA World Cup match schedule", "url": "#"},
        {"title": "FIFA World Cup Bracket 2026", "url": "#"},
        {"title": "8 most important players of the quarterfinals", "url": "#"},
        {"title": "Yellow card watch: WC QFs", "url": "#"},
    ]

    # FLAGS (replace with your own model later)
    france_flag = {
        "url": "https://flagcdn.com/w40/fr.png"
    }
    morocco_flag = {
        "url": "https://flagcdn.com/w40/ma.png"
    }

    match_time = "9:00 PM"

    categories = Category.objects.all()

    return render(
        request,
        'blog/home.html',
        {
            "hero_post": hero_post,
            "latest_posts": latest_posts,
            "popular_posts": popular_posts,
            "categories": categories,
            "slider_posts": slider_posts,
            "worldcup_posts": worldcup_posts,
            "bullet_links": bullet_links,
            "france_flag": france_flag,
            "morocco_flag": morocco_flag,
            "match_time": match_time,
        }
    )


def post_detail(request, slug):

    post = get_object_or_404(
        Post,
        slug=slug
    )

    post.views += 1
    post.save(update_fields=['views'])

    comments = post.comments.all()

    related_posts = Post.objects.filter(
        category=post.category
    ).exclude(
        id=post.id
    )[:4]

    if request.method == "POST":

        form = CommentForm(
            request.POST
        )

        if form.is_valid():

            comment = form.save(
                commit=False
            )

            comment.user = request.user
            comment.post = post

            comment.save()

            return redirect(
                'post_detail',
                slug=slug
            )

    else:

        form = CommentForm()

    return render(
        request,
        'blog/post_detail.html',
        {
            'post': post,
            'comments': comments,
            'form': form
        }
    )
    
def search_posts(request):

    query = request.GET.get('q', '')
    results = Post.objects.none()

    if query:
        results = Post.objects.filter(  
            Q(title__icontains=query) |
            Q(content__icontains=query) |
            Q(category__name__icontains=query) |
            Q(tags__name__icontains=query)
        ).distinct()

    return render(
        request,
        'blog/search_results.html',
        {
            'results': results,
            'query': query
        }
    )

@login_required
def post_create(request):
    if request.method == "POST":
        form = PostForm(request.POST, request.FILES)

        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user

            # Auto-generate slug if missing
            if not post.slug:
                post.slug = slugify(post.title)

            post.save()
            return redirect("post_detail", slug=post.slug)

    else:
        form = PostForm()

    return render(
        request,
        "blog/post_form.html",
        {
            "form": form,
            "title": "Create Post",
        }
    )


@login_required
def post_update(request, slug):
    post = get_object_or_404(Post, slug=slug)

    # Only author can edit
    if post.author != request.user:
        return redirect("post_detail", slug=slug)

    if request.method == "POST":
        form = PostForm(request.POST, request.FILES, instance=post)

        if form.is_valid():
            updated_post = form.save(commit=False)
            updated_post.slug = slugify(updated_post.title)
            updated_post.save()

            return redirect("post_detail", slug=updated_post.slug)

    else:
        form = PostForm(instance=post)

    return render(
        request,
        "blog/post_form.html",
        {
            "form": form,
            "title": "Edit Post",
            "post": post,
        }
    )


@login_required
def post_delete(request, slug):
    post = get_object_or_404(Post, slug=slug)

    # Only author can delete
    if post.author != request.user:
        return redirect("post_detail", slug=slug)

    if request.method == "POST":
        post.delete()
        return redirect("dashboard")

    return render(
        request,
        "blog/post_confirm_delete.html",
        {
            "post": post,
            "title": "Delete Post",
        }
    )


@login_required
def like_post(request, slug):

    post = get_object_or_404(
        Post,
        slug=slug
    )

    if request.user in post.likes.all():

        post.likes.remove(
            request.user
        )

    else:

        post.likes.add(
            request.user
        )

    html = render_to_string(
        'partials/like_button.html',
        {'post': post},
        request=request
    )

    return HttpResponse(html)

@login_required
def bookmark_post(request, slug):

    post = get_object_or_404(
        Post,
        slug=slug
    )

    bookmark, created = Bookmark.objects.get_or_create(
        user=request.user,
        post=post
    )

    if not created:
        bookmark.delete()

    return redirect(
        'post_detail',
        slug=slug
    )

def author_posts(request, username):

    author = get_object_or_404(
        User,
        username=username
    )

    posts = Post.objects.filter(
        author=author
    )
    
    popular_posts = Post.objects.order_by(
        '-views'
    )[:5]

    return render(
        request,
        'blog/author_posts.html',
        {
            'author': author,
            'posts': posts
        }
    )

def category_posts(request, slug):

    category = get_object_or_404(
        Category,
        slug=slug
    )

    posts = Post.objects.filter(
        category=category
    )

    return render(
        request,
        'blog/category_posts.html',
        {
            'category': category,
            'posts': posts
        }
    )

def tag_posts(request, slug):

    tag = get_object_or_404(
        Tag,
        slug=slug
    )

    posts = Post.objects.filter(
        tags__in=[tag]
    )

    return render(
        request,
        'blog/tag_posts.html',
        {
            'tag': tag,
            'posts': posts
        }
    )

@login_required
def dashboard(request):

    user_posts = Post.objects.filter(
        author=request.user
    )

    bookmarks = Bookmark.objects.filter(
        user=request.user
    )

    return render(
        request,
        'blog/dashboard.html',
        {
            'user_posts': user_posts,
            'bookmarks': bookmarks
        }
    )

@login_required
def saved_posts(request):

    bookmarks = Bookmark.objects.filter(
        user=request.user
    )

    return render(
        request,
        'blog/saved_posts.html',
        {
            'bookmarks': bookmarks
        }
    )

from django.http import HttpResponse

#def home(request):
 #   return HttpResponse("Blog homepage is working!")

