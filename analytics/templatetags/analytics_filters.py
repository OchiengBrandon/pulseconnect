from django import template

register = template.Library()

@register.filter
def filter_by_creator(reports, user):
    return reports.filter(creator=user)