"""Tests for the events app."""
from datetime import UTC, datetime, timedelta
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
from django.core.exceptions import ValidationError
from django.db.models import ProtectedError
from django.template.loader import render_to_string
from django.test import SimpleTestCase, TestCase
from django.urls import resolve, reverse

from . import views
from .models import Event, OrganizerAssignment

User = get_user_model()


def save_event(**changes):
    """Save a published event; keywords replace defaults."""
    fields = {
        'title': 'Python meetup',
        'starts_at': datetime(2026, 11, 19, 18, 30,
                              tzinfo=UTC),
        'timezone': 'Europe/London',
        'location': 'Leeds Central Library',
        'capacity': 40,
        'status': Event.Status.PUBLISHED,
    }
    fields.update(changes)
    fields.setdefault(
        'ends_at', fields['starts_at'] + timedelta(hours=2)
    )
    return Event.objects.create(**fields)


def layout_pages(event):
    """List the pages sharing the layout, for one event."""
    return [
        ('/', 'events/home.html', 'Otahque'),
        ('/events/', 'events/list.html',
         'Events | Otahque'),
        (f'/events/{event.pk}/', 'events/detail.html',
         'Python meetup | Otahque'),
    ]


class RoutingTests(TestCase):
    """Each address reaches its view; others are not found."""

    @classmethod
    def setUpTestData(cls):
        cls.event = save_event(title='Django workshop')

    def test_home(self):
        response = self.client.get('/')
        self.assertContains(
            response, 'Welcome to Otahque.'
        )
        self.assertEqual(reverse('events:home'), '/')
        self.assertIs(resolve('/').func, views.home)

    def test_event_list(self):
        response = self.client.get('/events/')
        self.assertContains(response, 'Django workshop')
        self.assertTemplateUsed(
            response, 'events/list.html'
        )
        self.assertContains(
            response, f'href="/events/{self.event.pk}/"'
        )
        self.assertEqual(
            reverse('events:list'), '/events/'
        )
        self.assertIs(
            resolve('/events/').func, views.event_list
        )

    def test_unknown_path(self):
        response = self.client.get('/does-not-exist/')
        self.assertEqual(response.status_code, 404)


class EventListTests(TestCase):
    """The list shows published events only."""

    @classmethod
    def setUpTestData(cls):
        save_event(
            title='Django workshop',
            starts_at=datetime(2026, 12, 3, 9,
                               tzinfo=UTC),
        )
        save_event(title='Python meetup')
        save_event(title='Spring planning',
                   status=Event.Status.DRAFT)
        save_event(title='Autumn social',
                   status=Event.Status.CANCELLED)

    def test_published_events_soonest_first(self):
        with self.assertNumQueries(1):
            response = self.client.get('/events/')
        html = response.content.decode()
        self.assertLess(html.index('Python meetup'),
                        html.index('Django workshop'))
        self.assertNotContains(response, 'Spring planning')
        self.assertNotContains(response, 'Autumn social')

    def test_empty_list(self):
        Event.objects.all().delete()
        response = self.client.get('/events/')
        self.assertContains(response, 'No events yet.')


class EventDetailTests(TestCase):
    """One published event by number; 404 for any other."""

    @classmethod
    def setUpTestData(cls):
        cls.event = save_event()

    def test_published_event(self):
        response = self.client.get(
            f'/events/{self.event.pk}/'
        )
        self.assertContains(
            response, '<h1>Python meetup</h1>', html=True
        )
        self.assertContains(
            response, 'Thursday 19 November 2026, 18:30 GMT'
        )
        self.assertContains(
            response, 'Thursday 19 November 2026, 20:30 GMT'
        )
        self.assertContains(
            response, 'Leeds Central Library'
        )
        self.assertTemplateUsed(
            response, 'events/detail.html'
        )

    def test_time_in_event_time_zone(self):
        event = save_event(
            starts_at=datetime(2026, 12, 3, 9,
                               tzinfo=UTC),
            timezone='Asia/Kolkata',
        )
        response = self.client.get(f'/events/{event.pk}/')
        self.assertContains(
            response, 'Thursday 3 December 2026, 14:30 IST'
        )

    def test_unpublished_events_are_hidden(self):
        response = self.client.get(
            f'/events/{self.event.pk}/'
        )
        self.assertContains(
            response, 'Leeds Central Library'
        )
        for status in (Event.Status.DRAFT,
                       Event.Status.CANCELLED):
            with self.subTest(status=status):
                event = save_event(status=status)
                response = self.client.get(
                    f'/events/{event.pk}/'
                )
                self.assertEqual(response.status_code, 404)

    def test_missing_event(self):
        self.assertIs(
            resolve('/events/999/').func,
            views.event_detail,
        )
        response = self.client.get('/events/999/')
        self.assertEqual(response.status_code, 404)

    def test_invalid_id(self):
        response = self.client.get('/events/abc/')
        self.assertEqual(response.status_code, 404)


class TemplateSafetyTests(TestCase):
    """Templates escape titles; an empty list says so."""

    @classmethod
    def setUpTestData(cls):
        cls.event = save_event(
            title='<strong>Not a tag</strong>'
        )

    def test_list_escapes_title(self):
        response = self.client.get('/events/')
        self.assertContains(
            response, '&lt;strong&gt;'
        )
        self.assertNotContains(
            response, '<strong>Not a tag'
        )

    def test_detail_escapes_title(self):
        response = self.client.get(
            f'/events/{self.event.pk}/'
        )
        self.assertContains(
            response, '&lt;strong&gt;'
        )
        self.assertNotContains(
            response, '<strong>Not a tag'
        )


class LayoutTests(TestCase):
    """Every page shares the base layout and navigation."""

    @classmethod
    def setUpTestData(cls):
        cls.pages = layout_pages(save_event())

    def test_pages_extend_layout(self):
        for url, template, title in self.pages:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertTemplateUsed(response, template)
                self.assertTemplateUsed(
                    response, 'base.html'
                )
                self.assertContains(
                    response, f'<title>{title}</title>',
                    html=True,
                )

    def test_pages_include_navigation(self):
        for url, template, title in self.pages:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertTemplateUsed(
                    response, 'includes/site_nav.html'
                )
                self.assertContains(
                    response,
                    '<a href="/">Home</a>',
                    html=True,
                )
                self.assertContains(
                    response,
                    '<a href="/events/">Events</a>',
                    html=True,
                )


class EventRowPartialTests(SimpleTestCase):
    """The event row partial renders one event."""

    def test_row_renders_alone(self):
        event = Event(pk=7, title='<b>Not a tag</b>')
        html = render_to_string(
            'events/list.html#event-row', {'event': event}
        )
        self.assertIn('href="/events/7/"', html)
        self.assertIn('&lt;b&gt;Not a tag', html)
        self.assertNotIn('<nav', html)


class StylesheetTests(TestCase):
    """Pages link the stylesheet, and Django can find it."""

    @classmethod
    def setUpTestData(cls):
        cls.pages = layout_pages(save_event())

    def test_pages_link_stylesheet(self):
        for url, template, title in self.pages:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertContains(
                    response,
                    '<link rel="stylesheet"'
                    ' href="/static/otahque/site.css">',
                    html=True,
                )

    def test_finder_locates_stylesheet(self):
        self.assertIsNotNone(
            finders.find('otahque/site.css')
        )


class DesignSystemTests(SimpleTestCase):
    """The navigation uses the design system navbar."""

    def test_navigation_uses_navbar(self):
        response = self.client.get('/')
        self.assertContains(
            response, '<nav class="site-nav navbar'
        )

    def test_stylesheet_defines_navbar(self):
        found = finders.find('otahque/site.css')
        css = Path(found).read_text(encoding='utf-8')
        self.assertTrue(
            '.navbar {' in css,
            'site.css has no .navbar rule',
        )


class OrganizerAssignmentTests(TestCase):
    """An assignment links an organizer to an event."""

    @classmethod
    def setUpTestData(cls):
        cls.event = save_event()
        cls.member = User.objects.create_user(
            'sam@example.org', display_name='Sam'
        )
        cls.assignment = OrganizerAssignment.objects.create(
            event=cls.event, member=cls.member
        )

    def test_assignment_links_event_and_member(self):
        assignment = self.assignment
        self.assertEqual(assignment.event, self.event)
        self.assertEqual(assignment.member, self.member)
        self.assertIsNone(assignment.revoked_at)
        self.assertQuerySetEqual(
            self.event.organizer_assignments.all(),
            [assignment],
        )
        self.assertQuerySetEqual(
            self.member.organizer_assignments.all(),
            [assignment],
        )

    def test_assigned_event_and_member_are_kept(self):
        for row in (self.event, self.member):
            model = type(row)
            with self.subTest(model=model.__name__):
                with self.assertRaises(ProtectedError):
                    row.delete()
                kept = model.objects.filter(pk=row.pk)
                self.assertTrue(kept.exists())

    def test_unlinked_event_can_be_deleted(self):
        spare = save_event(title='Spare event')
        self.assertEqual(
            spare.delete(), (1, {'events.Event': 1})
        )


class EventModelTests(SimpleTestCase):
    """The Event model's rules, checked without a database."""

    def make_event(self, **changes):
        """Make a valid unsaved event with these changes."""
        fields = {
            'title': 'Python meetup',
            'starts_at': datetime(2026, 11, 19, 18, 30,
                                  tzinfo=UTC),
            'ends_at': datetime(2026, 11, 19, 20, 30,
                                tzinfo=UTC),
            'timezone': 'Europe/London',
            'location': 'Virtual',
            'capacity': 40,
        }
        fields.update(changes)
        return Event(**fields)

    def test_str_is_title(self):
        event = self.make_event()
        self.assertEqual(str(event), 'Python meetup')

    def test_status_starts_draft_and_is_checked(self):
        event = self.make_event()
        self.assertEqual(event.status, Event.Status.DRAFT)
        event.full_clean()
        event.status = 'archived'
        with self.assertRaises(ValidationError) as caught:
            event.full_clean()
        self.assertEqual(
            caught.exception.message_dict,
            {'status': [
                "Value 'archived' is not a valid choice."
            ]},
        )
