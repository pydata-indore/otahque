from django.http import Http404
from django.shortcuts import render

SAMPLE_EVENTS = {1: 'Python meetup'}


def home(request):
    return render(request, 'events/home.html')


def event_list(request):
    events = [
        {'id': event_id, 'title': title}
        for event_id, title in SAMPLE_EVENTS.items()
    ]
    return render(
        request, 'events/list.html', {'events': events}
    )


def event_detail(request, event_id):
    title = SAMPLE_EVENTS.get(event_id)
    if title is None:
        raise Http404('Sample event not found')
    return render(
        request, 'events/detail.html', {'title': title}
    )
