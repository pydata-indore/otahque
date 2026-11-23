"""Models for Otahque's events."""
from django.conf import settings
from django.db import models
from django.utils import timezone


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
        return self.title


class OrganizerAssignment(models.Model):
    """Which member organizes which event, from the ERD."""

    event = models.ForeignKey(
        Event,
        on_delete=models.PROTECT,
        related_name='organizer_assignments',
    )
    member = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='organizer_assignments',
    )
    assigned_at = models.DateTimeField(
        default=timezone.now
    )
    revoked_at = models.DateTimeField(
        null=True, blank=True
    )

    class Meta:
        ordering = ['assigned_at']

    def __str__(self):
        return f'{self.member} organizes {self.event}'
