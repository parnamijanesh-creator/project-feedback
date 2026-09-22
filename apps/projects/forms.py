"""Forms for Project creation and Team Member management."""
from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q
from .models import Project, ProjectMember

User = get_user_model()

TAILWIND_INPUT_CLASSES = (
    "w-full px-3 py-2 border border-slate-300 rounded-lg shadow-sm placeholder-slate-400 "
    "focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 text-sm text-slate-800"
)
TAILWIND_SELECT_CLASSES = (
    "w-full px-3 py-2 border border-slate-300 rounded-lg shadow-sm bg-white "
    "focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 text-sm text-slate-800"
)


class ProjectForm(forms.ModelForm):
    """Form for creating a new project."""

    class Meta:
        model = Project
        fields = ["name", "description"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": TAILWIND_INPUT_CLASSES,
                    "placeholder": "e.g. Core Product Engineering",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": TAILWIND_INPUT_CLASSES,
                    "placeholder": "Brief description of the team or product scope...",
                    "rows": 3,
                }
            ),
        }


class AddProjectMemberForm(forms.Form):
    """Form for adding an existing user to a project roster."""

    identifier = forms.CharField(
        label="Username or Email",
        widget=forms.TextInput(
            attrs={
                "class": TAILWIND_INPUT_CLASSES,
                "placeholder": "username or user@example.com",
            }
        ),
    )
    role = forms.ChoiceField(
        choices=ProjectMember.Role.choices,
        initial=ProjectMember.Role.MEMBER,
        widget=forms.Select(attrs={"class": TAILWIND_SELECT_CLASSES}),
    )

    def __init__(self, *args, project=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.project = project

    def clean_identifier(self):
        identifier = self.cleaned_data.get("identifier", "").strip()
        user = User.objects.filter(
            Q(username__iexact=identifier) | Q(email__iexact=identifier)
        ).first()
        if not user:
            raise forms.ValidationError("User not found")

        if self.project and ProjectMember.objects.filter(project=self.project, user=user).exists():
            raise forms.ValidationError("User is already a member of this project")

        self.cleaned_user = user
        return identifier


class UpdateMemberRoleForm(forms.Form):
    """Form for updating an existing member's role."""

    role = forms.ChoiceField(
        choices=ProjectMember.Role.choices,
        widget=forms.Select(attrs={"class": TAILWIND_SELECT_CLASSES}),
    )
