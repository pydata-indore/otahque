"""Models for Otahque's events."""
from django.db import models


class Event(models.Model):
    """A proposed Otahque event, from the Chapter 15 ERD."""

    class Status(models.TextChoices):
        """Where an event is: draft, published, or cancelled."""

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
        """Return the event's title."""
        return self.title
