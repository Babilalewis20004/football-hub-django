from django.core.exceptions import PermissionDenied

class AuthorRequiredMixin:

    def dispatch(self, request, *args, **kwargs):

        if request.user.role not in ['author', 'editor', 'admin']:
            raise PermissionDenied

        return super().dispatch(
            request,
            *args,
            **kwargs
        )