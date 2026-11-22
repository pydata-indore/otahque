"""The events app's views: one function per page."""
from django.http import Http404
from django.shortcuts import render

SAMPLE_EVENTS = {1: 'Python meetup'}


def home(request):
    """Welcome visitors to Otahque."""
    return render(request, 'events/home.html')


def event_list(request):
    """List Otahque's events."""
    events = [
        {'id': event_id, 'title': title}
        for event_id, title in SAMPLE_EVENTS.items()
    ]
    return render(
        request, 'events/list.html', {'events': events}
    )


def event_detail(request, event_id):
    """Show one event, or 404 if its number is unknown."""
    title = SAMPLE_EVENTS.get(event_id)
    if title is None:
        raise Http404('Sample event not found')
    return render(
        request, 'events/detail.html', {'title': title}
    )
