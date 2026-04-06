from django import forms

from catalog.models import Record


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
            "title": forms.TextInput(attrs={"class": "w-full", "dir": "auto"}),
            "title_romanized": forms.TextInput(attrs={"class": "w-full"}),
            "subtitle": forms.TextInput(attrs={"class": "w-full", "dir": "auto"}),
            "date_of_publication": forms.NumberInput(attrs={"class": "w-32"}),
            "date_of_publication_display": forms.TextInput(
                attrs={"class": "w-full", "placeholder": "e.g. ca. 1850"}
            ),
            "place_of_publication": forms.TextInput(
                attrs={"class": "w-full", "dir": "auto"}
            ),
            "language": forms.TextInput(
                attrs={"class": "w-32", "placeholder": "e.g. heb, eng"}
            ),
            "notes": forms.Textarea(attrs={"class": "w-full", "rows": 3}),
        }
