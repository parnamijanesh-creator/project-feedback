"""Forms for user registration and authentication."""
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

User = get_user_model()

TAILWIND_INPUT_CLASSES = (
    "w-full px-3 py-2 border border-slate-300 rounded-lg shadow-sm placeholder-slate-400 "
    "focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 text-sm text-slate-800"
)


class UserRegistrationForm(UserCreationForm):
    """Registration form for new user accounts with Tailwind styling and email validation."""

    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(
            attrs={
                "class": TAILWIND_INPUT_CLASSES,
                "placeholder": "name@example.com",
                "autocomplete": "email",
            }
        ),
        help_text="A valid email address for notifications and account verification.",
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Apply Tailwind classes to username and password fields
        if "username" in self.fields:
            self.fields["username"].widget.attrs.update(
                {
                    "class": TAILWIND_INPUT_CLASSES,
                    "placeholder": "your_username",
                    "autocomplete": "username",
                }
            )
        if "password1" in self.fields:
            self.fields["password1"].widget.attrs.update(
                {
                    "class": TAILWIND_INPUT_CLASSES,
                    "placeholder": "••••••••",
                    "autocomplete": "new-password",
                }
            )
        if "password2" in self.fields:
            self.fields["password2"].widget.attrs.update(
                {
                    "class": TAILWIND_INPUT_CLASSES,
                    "placeholder": "••••••••",
                    "autocomplete": "new-password",
                }
            )

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if email and User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email

    def clean_username(self):
        username = self.cleaned_data.get("username")
        if username and User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("A user with this username already exists.")
        return username


class LoginForm(AuthenticationForm):
    """Login form styled with Tailwind CSS."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "username" in self.fields:
            self.fields["username"].widget.attrs.update(
                {
                    "class": TAILWIND_INPUT_CLASSES,
                    "placeholder": "Username",
                    "autocomplete": "username",
                }
            )
        if "password" in self.fields:
            self.fields["password"].widget.attrs.update(
                {
                    "class": TAILWIND_INPUT_CLASSES,
                    "placeholder": "Password",
                    "autocomplete": "current-password",
                }
            )
