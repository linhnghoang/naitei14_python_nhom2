from django import forms
from django.utils import timezone
from datetime import timedelta
from .models import BorrowRequest


class BorrowRequestForm(forms.ModelForm):
    requested_from = forms.DateField(
        widget=forms.DateInput(attrs={
            'type': 'date',
            'readonly': True,
        }),
        disabled=True,
    )

    class Meta:
        model = BorrowRequest
        fields = ['user', 'book_item', 'requested_from', 'duration', 'status']

    def clean_requested_from(self):
        """Validate that requested_from is today or tomorrow"""
        today = timezone.now().date()
        tomorrow = today + timedelta(days=1)

        # If editing existing object, don't validate
        if self.instance.pk:
            return self.instance.requested_from

        # For new objects, set to today by default
        requested_from = today

        # Check if it's in the past (should not happen since readonly)
        if requested_from < today:
            raise forms.ValidationError(
                "Borrow date cannot be in the past."
            )

        # Check if it's more than 1 day in the future
        if requested_from > tomorrow:
            raise forms.ValidationError(
                "Borrow date cannot be more than 1 day in the future."
            )

        return requested_from

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set requested_from to today if creating new object
        if not self.instance.pk:
            self.fields['requested_from'].initial = timezone.now().date()
            self.fields['requested_from'].widget.attrs['value'] = (
                timezone.now().date().isoformat()
            )
