"""Admin pages for events and their organizers."""
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.contrib import admin
from django.utils import timezone

from registrations.models import Registration

from .models import Event, OrganizerAssignment

UTC_HELP = "In UTC, not the event's own time zone."


class RegistrationInline(admin.TabularInline):
    """An event's registrations, shown as history."""

    model = Registration
    fields = ['member', 'status', 'registered_at',
              'cancelled_at']
    readonly_fields = fields
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        """Refuse adds: members register on the site."""
        return False

    def has_change_permission(self, request, obj=None):
        """Refuse changes: registrations are history."""
        return False

    def get_queryset(self, request):
        """Fetch each registration's member at once."""
        queryset = super().get_queryset(request)
        return queryset.select_related('member')


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    """Events, with local start times and places left."""

    list_display = ['title', 'status', 'start_utc',
                    'local_start', 'places', 'capacity']
    list_filter = ['status']
    search_fields = ['title', 'location']
    ordering = ['-starts_at']
    fields = ['title', 'status', 'starts_at', 'ends_at',
              'timezone', 'local_start', 'location',
              'capacity']
    readonly_fields = ['local_start']
    inlines = [RegistrationInline]
    actions = None

    def get_queryset(self, request):
        """Count places left in the same query."""
        queryset = super().get_queryset(request)
        return queryset.with_places()

    def get_form(self, request, obj=None, **kwargs):
        """Say on the form that both times are in UTC."""
        kwargs['help_texts'] = {
            'starts_at': UTC_HELP, 'ends_at': UTC_HELP,
        }
        return super().get_form(request, obj, **kwargs)

    @admin.display(description='Start (UTC)',
                   ordering='starts_at')
    def start_utc(self, event):
        """Return the start as stored, in UTC."""
        return event.starts_at

    @admin.display(description='Local start')
    def local_start(self, event):
        """Return the start in the event's zone, or None."""
        try:
            zone = ZoneInfo(event.timezone)
        except (ValueError, ZoneInfoNotFoundError):
            return None
        if event.starts_at is None:
            return None
        local = timezone.localtime(event.starts_at, zone)
        return local.strftime('%a %d %b %Y, %H:%M %Z')

    @admin.display(description='Places left',
                   ordering='places_left')
    def places(self, event):
        """Return the places left the queryset counted."""
        return event.places_left


@admin.register(OrganizerAssignment)
class OrganizerAssignmentAdmin(admin.ModelAdmin):
    """Assign organizers; revoke, but never delete."""

    list_display = ['event', 'member', 'assigned_at',
                    'revoked_at']
    list_filter = [
        ('revoked_at', admin.EmptyFieldListFilter),
    ]
    list_select_related = ['event', 'member']

    def get_fields(self, request, obj=None):
        """Return the event and member to add; all after."""
        if obj is None:
            return ['event', 'member']
        return ['event', 'member', 'assigned_at',
                'revoked_at']

    def get_readonly_fields(self, request, obj=None):
        """Return what is fixed: all but an open revoke time.

        Once revoked, the time is fixed too: clearing it would
        make the old assignment current again with no record.
        """
        if obj is None:
            return []
        if obj.revoked_at is not None:
            return ['event', 'member', 'assigned_at',
                    'revoked_at']
        return ['event', 'member', 'assigned_at']

    def has_delete_permission(self, request, obj=None):
        """Refuse deletes: revoke an assignment instead."""
        return False
