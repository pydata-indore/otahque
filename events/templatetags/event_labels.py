from django import template
from django.utils.html import format_html

register = template.Library()


@register.filter
def sample_label(title):
    """Mark a title as fictional sample data, escaping it."""
    return format_html(
        '<span class="sample-label">Sample:</span> {}', title
    )
