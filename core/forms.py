from django import forms


class CSVUploadForm(forms.Form):
    file = forms.FileField(help_text="Upload a CSV file")
