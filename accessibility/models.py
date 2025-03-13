# accessibility/models.py

from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()  # Get the custom user model

class AccessibilitySetting(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    high_contrast_mode = models.BooleanField(default=False)
    text_size = models.CharField(max_length=10, choices=[
        ('small', 'Small'),
        ('medium', 'Medium'),
        ('large', 'Large'),
    ], default='medium')

    def __str__(self):
        return f"{self.user.username}'s Accessibility Settings"