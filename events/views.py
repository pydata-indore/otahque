"""The events app's views: one function per page."""
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from .models import Event


def home(request):
    """Welcome visitors to Otahque."""
    return render(request, 'events/home.html')


def event_list(request):
    """List upcoming published events, then past ones."""
    now = timezone.now()
    events = Event.objects.published().with_places()
    return render(request, 'events/list.html', {
        'upcoming': events.upcoming(now),
        'past': events.past(now),
        'now': now,
    })


def event_detail(request, event_id):
    """Show one published event, or 404."""
    event = get_object_or_404(
        Event.objects.published().with_places(), pk=event_id
    )
    return render(request, 'events/detail.html', {
        'event': event,
        'now': timezone.now(),
    })
