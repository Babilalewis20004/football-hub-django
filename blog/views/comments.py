from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
import logging
logger = logging.getLogger("blog")


from blog.models import Post, Comment


@require_POST
@login_required
def delete_comment(request, pk):
    comment = get_object_or_404(Comment, pk=pk)

    if comment.user != request.user:
        return redirect("post_detail", slug=comment.post.slug)

    post_slug = comment.post.slug
    comment.delete()
    return redirect("post_detail", slug=post_slug)
