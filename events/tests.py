from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from django.contrib.staticfiles import finders
from django.core.exceptions import ValidationError
from django.template import Context, Template
from django.template.loader import render_to_string
from django.test import SimpleTestCase
from django.urls import resolve, reverse

from . import views
from .models import Event


class RoutingTests(SimpleTestCase):
    def test_home(self):
        response = self.client.get('/')
        self.assertContains(
            response, 'Welcome to Otahque.'
        )
        self.assertEqual(reverse('events:home'), '/')
        self.assertIs(resolve('/').func, views.home)

    def test_event_list(self):
        response = self.client.get('/events/')
        self.assertContains(response, 'Python meetup')
        self.assertTemplateUsed(
            response, 'events/list.html'
        )
        self.assertContains(
            response, 'href="/events/1/"'
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


class EventDetailTests(SimpleTestCase):
    def test_sample_event(self):
        response = self.client.get('/events/1/')
        self.assertContains(
            response,
            '<h1><span class="sample-label">Sample:</span>'
            ' Python meetup</h1>',
            html=True,
        )
        self.assertTemplateUsed(
            response, 'events/detail.html'
        )
        self.assertTrue(
            response['Content-Type'].startswith(
                'text/html'
            )
        )

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


class TemplateSafetyTests(SimpleTestCase):
    def test_empty_list(self):
        with patch.dict(
            views.SAMPLE_EVENTS, {}, clear=True
        ):
            response = self.client.get('/events/')
        self.assertContains(
            response, 'No sample events yet.'
        )

    def test_list_escapes_title(self):
        title = '<strong>Not a tag</strong>'
        with patch.dict(
            views.SAMPLE_EVENTS, {1: title}, clear=True
        ):
            response = self.client.get('/events/')
        self.assertContains(
            response, '&lt;strong&gt;'
        )
        self.assertNotContains(
            response, '<strong>Not a tag'
        )

    def test_detail_escapes_title(self):
        title = '<strong>Not a tag</strong>'
        with patch.dict(
            views.SAMPLE_EVENTS, {1: title}, clear=True
        ):
            response = self.client.get('/events/1/')
        self.assertContains(
            response, '&lt;strong&gt;'
        )
        self.assertNotContains(
            response, '<strong>Not a tag'
        )


class LayoutTests(SimpleTestCase):
    pages = [
        ('/', 'events/home.html', 'Otahque'),
        ('/events/', 'events/list.html',
         'Sample events | Otahque'),
        ('/events/1/', 'events/detail.html',
         'Sample event | Otahque'),
    ]

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
    def test_row_renders_alone(self):
        event = {'id': 1, 'title': '<b>Not a tag</b>'}
        html = render_to_string(
            'events/list.html#event-row', {'event': event}
        )
        self.assertIn('href="/events/1/"', html)
        self.assertIn('&lt;b&gt;Not a tag', html)
        self.assertNotIn('<nav', html)


class SampleLabelFilterTests(SimpleTestCase):
    def render_label(self, title):
        template = Template(
            '{% load event_labels %}{{ title|sample_label }}'
        )
        return template.render(Context({'title': title}))

    def test_labels_title(self):
        self.assertEqual(
            self.render_label('Python meetup'),
            '<span class="sample-label">Sample:</span>'
            ' Python meetup',
        )

    def test_escapes_title(self):
        title = '<strong>Not a tag</strong>'
        html = self.render_label(title)
        self.assertIn('&lt;strong&gt;', html)
        self.assertNotIn('<strong>', html)


class StylesheetTests(SimpleTestCase):
    def test_pages_link_stylesheet(self):
        for url, template, title in LayoutTests.pages:
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


class EventModelTests(SimpleTestCase):
    def make_event(self, **changes):
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

    def test_ends_at_after_starts_at(self):
        event = self.make_event()
        event.full_clean()

    def test_ends_at_before_starts_at_fails(self):
        event = self.make_event()
        event.starts_at = datetime(2026, 11, 19, 20, 30,
                                  tzinfo=UTC)
        event.ends_at = datetime(2026, 11, 19, 18, 30,
                                tzinfo=UTC)
        with self.assertRaises(ValidationError) as caught:
            event.full_clean()
        self.assertEqual(
            caught.exception.message_dict,
            {'ends_at': ['ends_at must be after starts_at']},
        )
