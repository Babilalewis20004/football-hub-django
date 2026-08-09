from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from .models import SUPPORT_ROLES


def is_support_agent(user):
    return user.is_authenticated and user.role in SUPPORT_ROLES


def support_agent_required(view_func):
    @login_required
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not is_support_agent(request.user):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return wrapped
