from django.core.exceptions import ValidationError
from django.db import models


class Event(models.Model):
    """A proposed Otahque event, from the Chapter 15 ERD."""

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        PUBLISHED = 'published', 'Published'
        CANCELLED = 'cancelled', 'Cancelled'

    title = models.CharField(max_length=200)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    timezone = models.CharField(max_length=64)
    location = models.CharField(max_length=200)
    capacity = models.PositiveIntegerField()
    status = models.CharField(
        max_length=20,
        choices=Status,
        default=Status.DRAFT,
    )

    class Meta:
        ordering = ['starts_at']

    def __str__(self):
        return self.title

    def clean(self):
        super().clean()
        if self.ends_at and self.starts_at:
            if self.ends_at <= self.starts_at:
                raise ValidationError(
                    {'ends_at': [
                        'ends_at must be after starts_at'
                    ]}
                )
