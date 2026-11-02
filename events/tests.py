from unittest.mock import patch

from django.test import SimpleTestCase
from django.urls import resolve, reverse

from . import views


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
            response, 'Sample: Python meetup'
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
