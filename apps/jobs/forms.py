from django import forms
from django.conf import settings


class UploadForm(forms.Form):
    image = forms.ImageField(required=True)
    mode = forms.ChoiceField(required=False)

    def __init__(self, *args, allowed_models=None, **kwargs):
        super().__init__(*args, **kwargs)
        allowed = allowed_models or settings.ALLOWED_REMBG_MODELS
        choices = [("u2netp", "Cepat")]
        if "isnet-general-use" in allowed:
            choices.append(("isnet-general-use", "Kualitas"))
        self.fields["mode"].choices = choices
        self.fields["mode"].initial = settings.DEFAULT_REMBG_MODEL
