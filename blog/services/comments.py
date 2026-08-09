def create_comment(post, user, form):
    comment = form.save(commit=False)
    comment.user = user
    comment.post = post
    comment.save()
    return comment
