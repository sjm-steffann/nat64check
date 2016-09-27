from datetime import timedelta

from django.contrib import admin
from django.db.models.aggregates import Avg, Count, Max, Min
from django.utils import timezone
from django.utils.safestring import mark_safe

from v6score.models import Measurement, Website


def show_score(score):
    if score is None:
        return '-'
    if score == 0:
        colour = 'red'
    elif score < 0.8:
        colour = 'orange'
    elif score < 0.95:
        colour = 'blue'
    else:
        colour = 'green'

    return mark_safe('<span style="color:{}">{:0.4f}</span>'.format(colour, score))


class InlineMeasurement(admin.TabularInline):
    model = Measurement
    fields = ('requested', 'started', 'finished', 'admin_v6only_score', 'admin_nat64_score')
    readonly_fields = ('requested', 'started', 'finished', 'admin_v6only_score', 'admin_nat64_score')
    can_delete = False
    show_change_link = True

    def has_add_permission(self, request):
        return False

    def admin_v6only_score(self, obj):
        return show_score(obj.v6only_score)

    admin_v6only_score.short_description = 'v6only score'

    def admin_nat64_score(self, obj):
        return show_score(obj.nat64_score)

    admin_nat64_score.short_description = 'nat64 score'


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


@admin.register(Website)
class WebsiteAdmin(admin.ModelAdmin):
    list_display = ('hostname', 'hash_param',
                    'measurement_count',
                    'last_test',
                    'min_v6only_score', 'avg_v6only_score', 'max_v6only_score',
                    'min_nat64_score', 'avg_nat64_score', 'max_nat64_score')
    list_filter = (LastTestFilter,)
    inlines = [InlineMeasurement]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(measurement_count=Count('measurement'),
                           last_test=Max('measurement__finished'),
                           min_v6only_score=Min('measurement__v6only_score'),
                           avg_v6only_score=Avg('measurement__v6only_score'),
                           max_v6only_score=Max('measurement__v6only_score'),
                           min_nat64_score=Min('measurement__nat64_score'),
                           avg_nat64_score=Avg('measurement__nat64_score'),
                           max_nat64_score=Max('measurement__nat64_score'))

    def measurement_count(self, obj):
        return obj.measurement_count

    measurement_count.admin_order_field = 'measurement_count'

    def last_test(self, obj):
        return obj.last_test

    last_test.admin_order_field = 'last_test'

    def min_v6only_score(self, obj):
        return show_score(obj.min_v6only_score)

    min_v6only_score.admin_order_field = 'min_v6only_score'

    def avg_v6only_score(self, obj):
        return show_score(obj.avg_v6only_score)

    avg_v6only_score.admin_order_field = 'avg_v6only_score'

    def max_v6only_score(self, obj):
        return show_score(obj.max_v6only_score)

    max_v6only_score.admin_order_field = 'max_v6only_score'

    def min_nat64_score(self, obj):
        return show_score(obj.min_nat64_score)

    min_nat64_score.admin_order_field = 'min_nat64_score'

    def avg_nat64_score(self, obj):
        return show_score(obj.avg_nat64_score)

    avg_nat64_score.admin_order_field = 'avg_nat64_score'

    def max_nat64_score(self, obj):
        return show_score(obj.max_nat64_score)

    max_nat64_score.admin_order_field = 'max_nat64_score'


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
                ('B', 'Bad'),
                ('G', 'Good'),
                ('P', 'Perfect'),
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


@admin.register(Measurement)
class MeasurementAdmin(admin.ModelAdmin):
    list_display = ('website', 'manual', 'requested', 'started', 'finished', 'admin_v6only_score', 'admin_nat64_score')
    date_hierarchy = 'finished'
    list_filter = ('manual', StateFilter, score_filter('v6only_score'), score_filter('nat64_score'))
    readonly_fields = ('requested', 'admin_images_inline',)

    fieldsets = [
        ('Test', {
            'fields': ('website', 'manual', 'requested', 'started', 'finished')
        }),
        ('Results', {
            'fields': ('v6only_score', 'nat64_score')
        }),
        ('Images', {
            'fields': ('admin_images_inline',)
        }),
    ]

    def admin_v6only_score(self, obj):
        return show_score(obj.v6only_score)

    admin_v6only_score.short_description = 'v6only score'

    def admin_nat64_score(self, obj):
        return show_score(obj.nat64_score)

    admin_nat64_score.short_description = 'nat64 score'

    def admin_images_inline(self, measurement):
        img = """<a href="{1}" target="_blank"><img style="width: 100%" alt="{0}" src="{1}"></a>"""

        return mark_safe("""
            <table style="border:0; width: 100%;">
                <tr>
                    <th style="text-align:center">IPv4-only</th>
                    <th style="text-align:center">IPv6-only</th>
                    <th style="text-align:center">NAT64</th>
                </tr>
                <tr>
                    <td style="width:33%">{v4only_image}</td>
                    <td style="width:33%">{v6only_image}</td>
                    <td style="width:33%">{nat64_image}</td>
                </tr>
            </table>
        """.format(
            v4only_image=img.format("IPv4-only", measurement.v4only_image.url) if measurement.v4only_image else '',
            v6only_image=img.format("IPv6-only", measurement.v6only_image.url) if measurement.v6only_image else '',
            nat64_image=img.format("NAT64", measurement.nat64_image.url) if measurement.nat64_image else '',
        ))

    admin_images_inline.short_description = 'Images'
