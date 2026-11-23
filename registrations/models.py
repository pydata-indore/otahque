"""Members' places at Otahque's events."""
from django.conf import settings
from django.db import models
from django.utils import timezone


class Registration(models.Model):
    """A member's place in an event, from the ERD."""

    class Status(models.TextChoices):
        """Whether the place is held: active or cancelled."""

        ACTIVE = 'active', 'Active'
        CANCELLED = 'cancelled', 'Cancelled'

    event = models.ForeignKey(
        'events.Event',
        on_delete=models.PROTECT,
        related_name='registrations',
    )
    member = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='registrations',
    )
    status = models.CharField(
        max_length=20,
        choices=Status,
        default=Status.ACTIVE,
    )
    registered_at = models.DateTimeField(
        default=timezone.now
    )
    cancelled_at = models.DateTimeField(
        null=True, blank=True
    )

    class Meta:
        ordering = ['registered_at']

    def __str__(self):
        return f'{self.member} at {self.event}'
