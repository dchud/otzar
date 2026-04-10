from django import forms

from catalog.models import Record

INPUT_CLASSES = (
    "w-full rounded border border-gray-300 dark:border-gray-500 "
    "bg-white dark:bg-gray-800 px-3 py-2 "
    "focus:outline-none focus:ring-2 focus:ring-blue-500"
)

INPUT_NARROW = INPUT_CLASSES.replace("w-full", "w-full sm:w-32")


class RecordForm(forms.ModelForm):
    """Form for manual entry and editing of bibliographic records."""

    author_name = forms.CharField(max_length=500, required=False)
    author_name_romanized = forms.CharField(max_length=500, required=False)
    publisher_name = forms.CharField(max_length=500, required=False)
    publisher_place = forms.CharField(max_length=255, required=False)
    location_label = forms.CharField(
        max_length=255,
        required=False,
        help_text="Physical location (e.g. Floor 1, Room B, Shelf 4a)",
    )

    class Meta:
        model = Record
        fields = [
            "title",
            "title_romanized",
            "subtitle",
            "date_of_publication",
            "date_of_publication_display",
            "place_of_publication",
            "language",
            "notes",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": INPUT_CLASSES, "dir": "auto"}),
            "title_romanized": forms.TextInput(attrs={"class": INPUT_CLASSES}),
            "subtitle": forms.TextInput(attrs={"class": INPUT_CLASSES, "dir": "auto"}),
            "date_of_publication": forms.NumberInput(attrs={"class": INPUT_NARROW}),
            "date_of_publication_display": forms.TextInput(
                attrs={"class": INPUT_CLASSES, "placeholder": "e.g. ca. 1850"}
            ),
            "place_of_publication": forms.TextInput(
                attrs={"class": INPUT_CLASSES, "dir": "auto"}
            ),
            "language": forms.HiddenInput(),
            "notes": forms.Textarea(attrs={"class": INPUT_CLASSES, "rows": 3}),
        }
