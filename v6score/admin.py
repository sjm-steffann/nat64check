import yaml
from django.contrib import admin
from django.db.models.aggregates import Avg, Count, Max, Min
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from pygments import highlight
from pygments.formatters.html import HtmlFormatter
from pygments.lexers.data import YamlLexer

from v6score.filter import LastTestFilter, RetryFilter, StateFilter, score_filter
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
    fields = ('requested', 'started', 'finished', 'admin_v6only_image_score', 'admin_nat64_image_score')
    readonly_fields = ('requested', 'started', 'finished', 'admin_v6only_image_score', 'admin_nat64_image_score')
    can_delete = False
    show_change_link = True

    def has_add_permission(self, request):
        return False

    def admin_v6only_image_score(self, obj):
        return show_score(obj.v6only_image_score)

    admin_v6only_image_score.short_description = 'v6only score'

    def admin_nat64_image_score(self, obj):
        return show_score(obj.nat64_image_score)

    admin_nat64_image_score.short_description = 'nat64 score'


@admin.register(Website)
class WebsiteAdmin(admin.ModelAdmin):
    list_display = ('hostname', 'hash_param',
                    'measurement_count',
                    'last_test',
                    'min_v6only_image_score', 'avg_v6only_image_score', 'max_v6only_image_score',
                    'min_nat64_image_score', 'avg_nat64_image_score', 'max_nat64_image_score')
    list_filter = (LastTestFilter,)
    inlines = [InlineMeasurement]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(measurement_count=Count('measurement'),
                           last_test=Max('measurement__finished'),
                           min_v6only_image_score=Min('measurement__v6only_image_score'),
                           avg_v6only_image_score=Avg('measurement__v6only_image_score'),
                           max_v6only_image_score=Max('measurement__v6only_image_score'),
                           min_nat64_image_score=Min('measurement__nat64_image_score'),
                           avg_nat64_image_score=Avg('measurement__nat64_image_score'),
                           max_nat64_image_score=Max('measurement__nat64_image_score'))

    def measurement_count(self, obj):
        return obj.measurement_count

    measurement_count.admin_order_field = 'measurement_count'

    def last_test(self, obj):
        return obj.last_test

    last_test.admin_order_field = 'last_test'

    def min_v6only_image_score(self, obj):
        return show_score(obj.min_v6only_image_score)

    min_v6only_image_score.admin_order_field = 'min_v6only_image_score'

    def avg_v6only_image_score(self, obj):
        return show_score(obj.avg_v6only_image_score)

    avg_v6only_image_score.admin_order_field = 'avg_v6only_image_score'

    def max_v6only_image_score(self, obj):
        return show_score(obj.max_v6only_image_score)

    max_v6only_image_score.admin_order_field = 'max_v6only_image_score'

    def min_nat64_image_score(self, obj):
        return show_score(obj.min_nat64_image_score)

    min_nat64_image_score.admin_order_field = 'min_nat64_image_score'

    def avg_nat64_image_score(self, obj):
        return show_score(obj.avg_nat64_image_score)

    avg_nat64_image_score.admin_order_field = 'avg_nat64_image_score'

    def max_nat64_image_score(self, obj):
        return show_score(obj.max_nat64_image_score)

    max_nat64_image_score.admin_order_field = 'max_nat64_image_score'


@admin.register(Measurement)
class MeasurementAdmin(admin.ModelAdmin):
    list_display = ('website', 'manual', 'admin_is_retry', 'retry_for',
                    'requested', 'started', 'finished',
                    'admin_v6only_image_score', 'admin_nat64_image_score',
                    'admin_v6only_resource_score', 'admin_nat64_resource_score')
    date_hierarchy = 'finished'
    list_filter = ('manual', RetryFilter, StateFilter,
                   score_filter('v6only_image_score'), score_filter('nat64_image_score'),
                   score_filter('v6only_resource_score'), score_filter('nat64_resource_score'))
    readonly_fields = ('requested', 'admin_images_inline',
                       'v6only_image_score', 'nat64_image_score',
                       'v6only_resource_score', 'nat64_resource_score',
                       'admin_v4only_resources', 'admin_v6only_resources', 'admin_nat64_resources',
                       'admin_v4only_data', 'v4only_data', 'v4only_debug',
                       'admin_v6only_data', 'v6only_data', 'v6only_debug',
                       'admin_nat64_data', 'nat64_data', 'nat64_debug')
    actions = ('mark_pending_as_manual',)
    search_fields = ('website__hostname',)

    fieldsets = [
        ('Test', {
            'fields': ('website', 'manual', 'requested', 'started', 'finished')
        }),
        ('Results', {
            'fields': (('v6only_image_score', 'nat64_image_score'),
                       ('v6only_resource_score', 'nat64_resource_score'),
                       ('admin_v4only_resources', 'admin_v6only_resources', 'admin_nat64_resources'))
        }),
        ('Images', {
            'fields': ('admin_images_inline',)
        }),
        ('Raw IPv4 data', {
            'fields': ('admin_v4only_data', 'v4only_debug'),
            'classes': ['collapse'],
        }),
        ('Raw IPv6 data', {
            'fields': ('admin_v6only_data', 'v6only_debug'),
            'classes': ['collapse'],
        }),
        ('Raw NAT64 data', {
            'fields': ('admin_nat64_data', 'nat64_debug'),
            'classes': ['collapse'],
        }),
    ]

    # noinspection PyMethodMayBeStatic
    def mark_pending_as_manual(self, request, queryset):
        pending = queryset.filter(started=None)
        pending.update(manual=True)
        self.message_user(request, "{} pending measurements marked as manual".format(pending.count()))

    def admin_is_retry(self, obj):
        return obj.retry_for is not None

    admin_is_retry.short_description = 'is retry'
    admin_is_retry.boolean = True

    def admin_v6only_image_score(self, obj):
        return show_score(obj.v6only_image_score)

    admin_v6only_image_score.short_description = 'v6only image score'

    def admin_nat64_image_score(self, obj):
        return show_score(obj.nat64_image_score)

    admin_nat64_image_score.short_description = 'nat64 image score'

    def admin_v6only_resource_score(self, obj):
        return show_score(obj.v6only_resource_score)

    admin_v6only_resource_score.short_description = 'v6only resource score'

    def admin_nat64_resource_score(self, obj):
        return show_score(obj.nat64_resource_score)

    admin_nat64_resource_score.short_description = 'nat64 resource score'

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

    def admin_v4only_resources(self, measurement):
        ok, error = measurement.v4only_resources
        return format_html("<b style='display:inline-block; width: 40px'>Ok:</b> {}<br>"
                           "<b style='display:inline-block; width: 40px'>Error:</b> {}", ok, error)

    admin_v4only_resources.short_description = 'v4only resources'

    def admin_v6only_resources(self, measurement):
        ok, error = measurement.v6only_resources
        return format_html("<b style='display:inline-block; width: 40px'>Ok:</b> {}<br>"
                           "<b style='display:inline-block; width: 40px'>Error:</b> {}", ok, error)

    admin_v6only_resources.short_description = 'v6only resources'

    def admin_nat64_resources(self, measurement):
        ok, error = measurement.nat64_resources
        return format_html("<b style='display:inline-block; width: 40px'>Ok:</b> {}<br>"
                           "<b style='display:inline-block; width: 40px'>Error:</b> {}", ok, error)

    admin_nat64_resources.short_description = 'nat64 resources'

    def admin_v4only_data(self, measurement):
        response = yaml.dump(measurement.v4only_data)

        # Get the Pygments formatter
        formatter = HtmlFormatter(style='colorful')

        # Highlight the data
        response = highlight(response, YamlLexer(), formatter)

        # Get the stylesheet
        style = "<style>" + formatter.get_style_defs() + "</style><br>"

        # Safe the output
        return mark_safe(style + response)

    admin_v4only_data.short_description = 'v4only data'

    def admin_v6only_data(self, measurement):
        response = yaml.dump(measurement.v6only_data)

        # Get the Pygments formatter
        formatter = HtmlFormatter(style='colorful')

        # Highlight the data
        response = highlight(response, YamlLexer(), formatter)

        # Get the stylesheet
        style = "<style>" + formatter.get_style_defs() + "</style><br>"

        # Safe the output
        return mark_safe(style + response)

    admin_v6only_data.short_description = 'v6only data'

    def admin_nat64_data(self, measurement):
        response = yaml.dump(measurement.nat64_data)

        # Get the Pygments formatter
        formatter = HtmlFormatter(style='colorful')

        # Highlight the data
        response = highlight(response, YamlLexer(), formatter)

        # Get the stylesheet
        style = "<style>" + formatter.get_style_defs() + "</style><br>"

        # Safe the output
        return mark_safe(style + response)

    admin_nat64_data.short_description = 'nat64 data'

    admin_images_inline.short_description = 'Images'
