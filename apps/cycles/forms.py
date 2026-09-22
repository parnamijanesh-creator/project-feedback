"""Forms for FeedbackCycle creation and status transitions."""
from django import forms
from .models import FeedbackCycle, get_current_week_start

TAILWIND_INPUT_CLASSES = (
    "w-full px-3 py-2 border border-slate-300 rounded-lg shadow-sm placeholder-slate-400 "
    "focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 text-sm text-slate-800"
)
TAILWIND_SELECT_CLASSES = (
    "w-full px-3 py-2 border border-slate-300 rounded-lg shadow-sm bg-white "
    "focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 text-sm text-slate-800"
)


class FeedbackCycleCreateForm(forms.ModelForm):
    """Form for starting a new weekly feedback cycle."""

    allow_concurrent = forms.BooleanField(
        required=False,
        label="Start anyway despite another active cycle",
        help_text="Check to proceed if another cycle is still collecting feedback.",
    )

    week_date = forms.DateField(
        required=False,
        widget=forms.DateInput(
            attrs={
                "type": "date",
                "class": TAILWIND_INPUT_CLASSES,
            }
        ),
    )

    class Meta:
        model = FeedbackCycle
        fields = ["week_date"]

    def __init__(self, *args, project=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.project = project
        if not self.initial.get("week_date"):
            self.initial["week_date"] = get_current_week_start().isoformat()

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get("week_date"):
            cleaned_data["week_date"] = get_current_week_start()

        if self.project:
            active_collecting = FeedbackCycle.objects.filter(
                project=self.project, status=FeedbackCycle.Status.COLLECTING
            ).exists()
            allow_concurrent = cleaned_data.get("allow_concurrent", False)

            if active_collecting and not allow_concurrent:
                raise forms.ValidationError(
                    "An active feedback cycle is currently collecting submissions for this project. "
                    "Please transition or complete the active cycle first, or confirm duplicate creation."
                )

        return cleaned_data


class CycleStatusTransitionForm(forms.Form):
    """Form for transitioning cycle phases."""

    status = forms.ChoiceField(
        choices=FeedbackCycle.Status.choices,
        widget=forms.Select(attrs={"class": TAILWIND_SELECT_CLASSES}),
    )
