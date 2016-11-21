from datetime import timedelta

from django.contrib import admin
from django.utils import timezone


class LastTestFilter(admin.SimpleListFilter):
    title = 'last test'
    parameter_name = 'last'

    def lookups(self, request, model_admin):
        return (
            ('T', 'Today'),
            ('W', 'Last 7 days'),
            ('MW', 'More than a week ago'),
            ('MM', 'More than a month ago'),
            ('MY', 'More than a year ago'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'T':
            limit = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
            return queryset.filter(measurement__finished__gte=limit)
        elif self.value() == 'W':
            limit = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=7)
            return queryset.filter(measurement__finished__gte=limit)
        elif self.value() == 'MW':
            limit = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=7)
            return queryset.exclude(measurement__finished__gte=limit)
        elif self.value() == 'MM':
            limit = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=30)
            return queryset.exclude(measurement__finished__gte=limit)
        elif self.value() == 'MY':
            limit = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=365)
            return queryset.exclude(measurement__finished__gte=limit)
        else:
            return queryset


class RetryFilter(admin.SimpleListFilter):
    title = 'retry'
    parameter_name = 'retry'

    def lookups(self, request, model_admin):
        return (
            ('Y', 'Is a retry'),
            ('N', 'Is not a retry'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'Y':
            return queryset.exclude(retry_for=None)
        elif self.value() == 'N':
            return queryset.filter(retry_for=None)
        else:
            return queryset


class StateFilter(admin.SimpleListFilter):
    title = 'state'
    parameter_name = 'state'

    def lookups(self, request, model_admin):
        return (
            ('R', 'Requested'),
            ('S', 'Started'),
            ('F', 'Finished'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'R':
            return queryset.filter(started=None, finished=None)
        elif self.value() == 'S':
            return queryset.exclude(started=None).filter(finished=None)
        elif self.value() == 'F':
            return queryset.exclude(finished=None)
        else:
            return queryset


def score_filter(attribute):
    class ScoreFilter(admin.SimpleListFilter):
        title = attribute.replace('_', ' ')
        parameter_name = attribute

        def lookups(self, request, model_admin):
            return (
                ('N', 'Untested'),
                ('U', 'Unreachable'),
                ('B', 'Poor'),
                ('G', 'Mediocre'),
                ('P', 'Good'),
            )

        def queryset(self, request, queryset):
            if self.value() == 'N':
                condition = {attribute: None}
            elif self.value() == 'U':
                condition = {attribute: 0}
            elif self.value() == 'B':
                condition = {attribute + '__gt': 0, attribute + '__lt': 0.8}
            elif self.value() == 'G':
                condition = {attribute + '__gte': 0.8, attribute + '__lt': 0.95}
            elif self.value() == 'P':
                condition = {attribute + '__gte': 0.95}
            else:
                return queryset

            return queryset.filter(**condition)

    return ScoreFilter
