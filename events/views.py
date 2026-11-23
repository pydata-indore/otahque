"""The events app's views: one function per page."""
from django.shortcuts import get_object_or_404, render

from .models import Event


def home(request):
    """Welcome visitors to Otahque."""
    return render(request, 'events/home.html')


def event_list(request):
    """List the published events."""
    events = Event.objects.filter(
        status=Event.Status.PUBLISHED
    )
    return render(
        request, 'events/list.html', {'events': events}
    )


def event_detail(request, event_id):
    """Show one published event, or 404."""
    event = get_object_or_404(
        Event, pk=event_id, status=Event.Status.PUBLISHED
    )
    return render(
        request, 'events/detail.html', {'event': event}
    )
