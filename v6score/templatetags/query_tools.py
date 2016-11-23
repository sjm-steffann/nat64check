from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def append_to_query(context, **kwargs):
    request = context['request']
    updated = request.GET.copy()

    # The update method appends to the MultiValueDict, it doesn't overwrite
    updated.update(kwargs)

    return updated.urlencode()


@register.simple_tag(takes_context=True)
def override_in_query(context, **kwargs):
    request = context['request']

    updated = request.GET.copy()
    # Setting a value overwrites existing values
    for key, value in kwargs.items():
        updated[key] = value

    return updated.urlencode()
