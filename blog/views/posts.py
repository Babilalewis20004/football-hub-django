from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import permission_required, login_required
from django.views.decorators.http import require_POST
from django.http import HttpResponseForbidden
from django.db.models import F, Q
from django.utils import timezone
import logging

logger = logging.getLogger("blog")
security_logger = logging.getLogger("security")

from blog.models import Post, Notification, Bookmark
from blog.forms import PostForm, CommentForm
from blog.services.posts import get_related_posts, can_view_post
from blog.services.comments import create_comment
from blog.services.telegram import send_new_post_announcement


# ---------------------------------------------------------
# POST DETAIL (public)
# ---------------------------------------------------------

def post_detail(request, slug):
    post = get_object_or_404(Post, slug=slug)

    # 🔒 Hide drafts & pending posts from the public
    if not can_view_post(request.user, post):
        return HttpResponseForbidden("This post is not published yet.")

    # atomic view increment
    Post.objects.filter(id=post.id).update(views=F("views") + 1)
    logger.info(f"Post viewed: {post.title} by {request.user if request.user.is_authenticated else 'Anonymous'}")

    comments = post.comments.all()
    related_posts = get_related_posts(post)

    is_bookmarked = (
        request.user.is_authenticated
        and Bookmark.objects.filter(user=request.user, post=post).exists()
    )
    bookmark_count = post.bookmarked_by.count()

    form = CommentForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        if not request.user.is_authenticated:
            security_logger.warning(f"Unauthenticated user attempted to comment on {post.slug}")
            return redirect("login")

        create_comment(post=post, user=request.user, form=form)
        logger.info(f"Comment added by {request.user.username} on post {post.slug}")
        return redirect("post_detail", slug=slug)

    return render(
        request,
        "blog/post_detail.html",
        {
            "post": post,
            "comments": comments,
            "form": form,
            "related_posts": related_posts,
            "is_bookmarked": is_bookmarked,
            "bookmark_count": bookmark_count,
        }
    )


# ---------------------------------------------------------
# CREATE POST (Admin, Editor, Author, Contributor)
# ---------------------------------------------------------

@login_required
@permission_required("blog.add_post", raise_exception=True)
def post_create(request):
    form = PostForm(request.POST or None, request.FILES or None)

    if request.method == "POST" and form.is_valid():
        post = form.save(commit=False)
        post.author = request.user

        post.status = "draft"
        post.is_published = False
        post.is_approved = False

        post.save()
        form.save_m2m()

        Notification.objects.create(
        user=request.user,
        message=f"Your post '{post.title}' is saved as a draft."
        )

        logger.info(f"Post created: {post.title} by {request.user.username}")

        return redirect("post_detail", slug=post.slug)

    return render(
        request,
        "blog/post_form.html",
        {
            "form": form,
            "title": "Create Post",
        }
    )


# ---------------------------------------------------------
# UPDATE POST
# Admin + Editor → can edit ANY post
# Author + Contributor → can edit ONLY their own post
# Reader → cannot edit
# ---------------------------------------------------------

@login_required
def post_update(request, slug):
    post = get_object_or_404(Post, slug=slug)

    # Admin + Editor can edit any post
    if request.user.has_perm("blog.change_post"):
        pass
    else:
        # Author + Contributor can only edit their own posts
        if post.author != request.user:
            security_logger.warning(
                f"Unauthorized edit attempt by {request.user.username} on post {post.slug}"
            )

            return HttpResponseForbidden("You cannot edit another user's post.")

        if post.author == request.user and post.is_published:

            return HttpResponseForbidden("You cannot edit a published post.")


    form = PostForm(request.POST or None, request.FILES or None, instance=post)

    if request.method == "POST" and form.is_valid():
        updated_post = form.save(commit=False)
        updated_post.save()
        form.save_m2m()
        logger.info(f"Post updated: {updated_post.title} by {request.user.username}")

        return redirect("post_detail", slug=updated_post.slug)

    return render(
        request,
        "blog/post_form.html",
        {
            "form": form,
            "title": "Edit Post",
            "post": post,
        }
    )


@require_POST
@permission_required("blog.can_publish_post")
def post_publish(request, slug):
    post = get_object_or_404(Post, slug=slug)

    now = timezone.now()
    post.is_published = True
    post.is_approved = True
    post.status = "published"
    post.published_at = now
    post.status_changed_at = now

    sent = send_new_post_announcement(post, request.build_absolute_uri(post.get_absolute_url()))
    if sent:
        post.telegram_announced_at = now

    post.save()

    Notification.objects.create(
    user=post.author,
    message=f"Your post '{post.title}' is now published!"
    )

    logger.info(f"Post published: {post.title} by {request.user.username}")
    return redirect("post_detail", slug=post.slug)


@require_POST
@permission_required("blog.can_approve_post")
def post_approve(request, slug):
    post = get_object_or_404(Post, slug=slug)

    post.is_approved = True
    if not post.is_published:
        post.status = "approved"
    post.status_changed_at = timezone.now()
    post.save()

    Notification.objects.create(
    user=post.author,
    message=f"Your post '{post.title}' was approved and is pending publication."
    )

    logger.info(f"Post approved: {post.title} by {request.user.username}")
    return redirect("post_detail", slug=post.slug)


@require_POST
@permission_required("blog.can_approve_post")
def post_request_changes(request, slug):
    post = get_object_or_404(Post, slug=slug)

    feedback = request.POST.get("feedback", "").strip()

    post.status = "needs_changes"
    post.is_approved = False
    post.editor_feedback = feedback
    post.status_changed_at = timezone.now()
    post.save()

    Notification.objects.create(
        user=post.author,
        message=f"Changes requested on '{post.title}': {feedback}" if feedback
        else f"Changes requested on '{post.title}'.",
    )

    logger.info(f"Changes requested on: {post.title} by {request.user.username}")
    return redirect("editor_dashboard")


@require_POST
@login_required
def post_submit_for_review(request, slug):
    post = get_object_or_404(Post, slug=slug)

    if post.author != request.user:
        security_logger.warning(
            f"Unauthorized submit-for-review attempt by {request.user.username} on post {post.slug}"
        )
        return HttpResponseForbidden("You cannot submit another user's post for review.")

    if post.status not in ("draft", "needs_changes"):
        return HttpResponseForbidden("This post cannot be submitted for review right now.")

    post.status = "in_review"
    post.status_changed_at = timezone.now()
    post.save()

    Notification.objects.create(
        user=post.author,
        message=f"Your post '{post.title}' was submitted for review."
    )

    logger.info(f"Post submitted for review: {post.title} by {request.user.username}")
    return redirect("author_dashboard")


@require_POST
@login_required
def post_withdraw_from_review(request, slug):
    post = get_object_or_404(Post, slug=slug)

    if post.author != request.user:
        security_logger.warning(
            f"Unauthorized withdraw-from-review attempt by {request.user.username} on post {post.slug}"
        )
        return HttpResponseForbidden("You cannot withdraw another user's post from review.")

    if post.status != "in_review":
        return HttpResponseForbidden("This post is not in review.")

    post.status = "draft"
    post.status_changed_at = timezone.now()
    post.save()

    logger.info(f"Post withdrawn from review: {post.title} by {request.user.username}")
    return redirect("author_dashboard")


@permission_required("blog.delete_post", raise_exception=True)
def post_delete(request, slug):
    post = get_object_or_404(Post, slug=slug)

    if request.method == "POST":
        logger.warning(f"Post deleted: {post.title} by {request.user.username}")
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

# ---------------------------------------------------------
#  Editor && Author Dashboard
# ---------------------------------------------------------

def _editor_dashboard_context(request):
    status_filter = request.GET.get("status", "")
    query = request.GET.get("q", "").strip()

    posts = Post.objects.all()
    if query:
        posts = posts.filter(Q(title__icontains=query))

    def bucket(*statuses):
        qs = posts.filter(status__in=statuses).order_by("-status_changed_at", "-created_at")
        if status_filter and status_filter not in statuses:
            return qs.none()
        return qs

    drafts = bucket("draft", "needs_changes")
    in_review = bucket("in_review")
    approved = bucket("approved")
    published = bucket("published")[:20]

    recent_activity = Post.objects.order_by("-status_changed_at", "-created_at")[:8]

    return {
        "drafts": drafts,
        "in_review": in_review,
        "approved": approved,
        "published": published,
        "recent_activity": recent_activity,
        "status_filter": status_filter,
        "query": query,
        "counts": {
            "all": posts.count(),
            "draft": posts.filter(status__in=["draft", "needs_changes"]).count(),
            "in_review": posts.filter(status="in_review").count(),
            "approved": posts.filter(status="approved").count(),
            "published": posts.filter(status="published").count(),
        },
    }


@login_required
@permission_required("blog.can_approve_post")
def editor_dashboard(request):
    notifications = list(Notification.objects.filter(user=request.user, is_read=False))
    # Mark notifications as read once dashboard is opened
    Notification.objects.filter(id__in=[n.id for n in notifications]).update(is_read=True)

    context = _editor_dashboard_context(request)
    context.update({
        "notifications": notifications,
        "title": "Editor Dashboard",
    })

    return render(request, "blog/editor_dashboard.html", context)


@login_required
@permission_required("blog.can_approve_post")
def editor_dashboard_partial(request):
    return render(
        request,
        "blog/partials/editor_dashboard_lists.html",
        _editor_dashboard_context(request),
    )


def _author_dashboard_context(request):
    status_filter = request.GET.get("status", "")
    query = request.GET.get("q", "").strip()

    posts = Post.objects.filter(author=request.user)
    if query:
        posts = posts.filter(Q(title__icontains=query))

    def bucket(*statuses):
        qs = posts.filter(status__in=statuses).order_by("-status_changed_at", "-created_at")
        if status_filter and status_filter not in statuses:
            return qs.none()
        return qs

    drafts = bucket("draft")
    needs_changes = bucket("needs_changes")
    in_review = bucket("in_review", "approved")
    published = bucket("published")

    return {
        "drafts": drafts,
        "needs_changes": needs_changes,
        "in_review": in_review,
        "published": published,
        "status_filter": status_filter,
        "query": query,
        "counts": {
            "all": posts.count(),
            "draft": posts.filter(status="draft").count(),
            "in_review": posts.filter(status__in=["in_review", "approved"]).count(),
            "needs_changes": posts.filter(status="needs_changes").count(),
            "published": posts.filter(status="published").count(),
        },
    }


@login_required
@permission_required("blog.add_post", raise_exception=True)
def author_dashboard(request):
    notifications = list(Notification.objects.filter(user=request.user, is_read=False))
    Notification.objects.filter(id__in=[n.id for n in notifications]).update(is_read=True)

    context = _author_dashboard_context(request)
    context.update({
        "notifications": notifications,
        "title": "My Posts",
    })

    return render(request, "blog/author_dashboard.html", context)


@login_required
@permission_required("blog.add_post", raise_exception=True)
def author_dashboard_partial(request):
    return render(
        request,
        "blog/partials/author_dashboard_lists.html",
        _author_dashboard_context(request),
    )