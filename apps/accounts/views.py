"""Views for user registration, authentication, and session termination."""
from django.contrib.auth import login as auth_login
from django.contrib.auth.views import LoginView as BaseLoginView, LogoutView as BaseLogoutView
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView

from .forms import LoginForm, UserRegistrationForm


class RegisterView(CreateView):
    """User registration view rendering registration form and auto-logging in upon success."""

    form_class = UserRegistrationForm
    template_name = "accounts/register.html"
    success_url = reverse_lazy("home")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("home")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        self.object = form.save()
        auth_login(self.request, self.object)
        return redirect(self.get_success_url())


class LoginView(BaseLoginView):
    """User login view with Tailwind styling, validation, and safe next redirection."""

    form_class = LoginForm
    template_name = "accounts/login.html"
    redirect_authenticated_user = True

    def get_default_redirect_url(self):
        return str(reverse_lazy("home"))


class LogoutView(BaseLogoutView):
    """User logout view expiring session on POST request and redirecting to login."""

    next_page = reverse_lazy("login")
