# Create your views here.
from django.shortcuts import render
from django.shortcuts import redirect

from django.contrib.auth import login

from django.contrib.auth.decorators import login_required

from .forms import RegisterForm
from .forms import ProfileUpdateForm


def register(request):

    if request.method == "POST":

        form = RegisterForm(request.POST)

        if form.is_valid():

            user = form.save()

            login(request, user)

            return redirect('/')

    else:
        form = RegisterForm()

    return render(
        request,
        'users/register.html',
        {'form': form}
    )


@login_required
def profile(request):

    if request.method == "POST":

        form = ProfileUpdateForm(
            request.POST,
            request.FILES,
            instance=request.user
        )

        if form.is_valid():

            form.save()

            return redirect('profile')

    else:

        form = ProfileUpdateForm(
            instance=request.user
        )

    return render(
        request,
        'users/profile.html',
        {'form': form}
    )