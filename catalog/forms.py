from django import forms
from django.utils import timezone
from .models import BorrowRequest


class BorrowRequestForm(forms.ModelForm):
    requested_from = forms.DateField(
        widget=forms.DateInput(
            attrs={
                "type": "date",
                "readonly": True,
            }
        ),
        disabled=True,
    )

    class Meta:
        model = BorrowRequest
        fields = ["user", "book_item", "requested_from", "duration", "status"]

    def clean_requested_from(self):
        """Validate that requested_from is today or tomorrow."""
        today = timezone.now().date()

        # If editing existing object, don't validate - keep original value
        if self.instance.pk:
            return self.instance.requested_from

        # For new objects, always use today as the value
        # (field is readonly, so we enforce this server-side)
        return today

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set requested_from to today if creating new object
        if not self.instance.pk:
            self.fields["requested_from"].initial = timezone.now().date()
            self.fields["requested_from"].widget.attrs["value"] = (
                timezone.now().date().isoformat()
            )
