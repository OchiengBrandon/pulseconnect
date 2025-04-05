from django import template

register = template.Library()

@register.filter
def filter_by_creator(reports, user):
    """Filter reports by the specified creator."""
    return reports.filter(creator=user)

@register.filter
def replace(value, arg):
    """Replace occurrences of a substring with another substring."""
    try:
        old, new = arg.split(":")
        return value.replace(old, new)
    except ValueError:
        return value  # or return a default value if the format is incorrect

@register.filter
def filter_active(jobs):
    """Filter jobs to return only active ones."""
    return jobs.filter(is_active=True)

@register.filter
def filter_completed(jobs):
    """Filter jobs to return only completed ones."""
    return jobs.filter(status='completed')  # Adjust according to your model's field