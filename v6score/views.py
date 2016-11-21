from django.db.models.query_utils import Q
from django.shortcuts import render, get_object_or_404, redirect

from v6score.forms import URLForm
from v6score.models import Measurement


def show_overview(request):
    if request.method == 'POST':
        url_form = URLForm(request.POST)
        if url_form.is_valid():
            # Get the cleaned URL from the form
            url = url_form.cleaned_data['url']
            force_new = url_form.cleaned_data['force_new']

            measurement = Measurement.objects.get_measurement_for_url(url, force_new)
            return redirect(measurement)
    else:
        url_form = URLForm()

    search_filter = request.GET.get('search', '').strip()
    test_filter = request.GET.get('test', '').strip()
    score_filter = request.GET.get('score', '').strip()

    nat64_selected = (test_filter == 'nat64')
    ipv6_selected = (test_filter == 'ipv6')
    poor_selected = (score_filter == 'poor')
    good_selected = (score_filter == 'good')
    perfect_selected = (score_filter == 'perfect')

    measurements = (Measurement.objects.all()
                    .exclude(finished=None)
                    .exclude(v6only_image_score=None, nat64_image_score=None)
                    .order_by('-finished'))

    if search_filter:
        measurements = measurements.filter(url__contains=search_filter)

    if nat64_selected:
        if poor_selected:
            measurements = measurements.filter(nat64_image_score__lt=0.8)
        elif good_selected:
            measurements = measurements.filter(nat64_image_score__gte=0.8, nat64_image_score__lt=0.95)
        elif perfect_selected:
            measurements = measurements.filter(nat64_image_score__gte=0.95)
        else:
            measurements = measurements.exclude(nat64_image_score=None)
    elif ipv6_selected:
        if poor_selected:
            measurements = measurements.filter(v6only_image_score__lt=0.8)
        elif good_selected:
            measurements = measurements.filter(v6only_image_score__gte=0.8, v6only_image_score__lt=0.95)
        elif perfect_selected:
            measurements = measurements.filter(v6only_image_score__gte=0.95)
        else:
            measurements = measurements.exclude(v6only_image_score=None)
    else:
        if poor_selected:
            measurements = measurements.filter(Q(nat64_image_score__lt=0.8) | Q(v6only_image_score__lt=0.8))
        elif good_selected:
            measurements = measurements.filter(Q(nat64_image_score__gte=0.8, nat64_image_score__lt=0.95,
                                                 v6only_image_score__gte=0.8) |
                                               Q(v6only_image_score__gte=0.8, v6only_image_score__lt=0.95,
                                                 nat64_image_score__gte=0.8))
        elif perfect_selected:
            measurements = measurements.filter(nat64_image_score__gte=0.95, v6only_image_score__gte=0.95)

    return render(request, 'v6score/overview.html', {
        'url_form': url_form,

        'search': search_filter,
        'test': test_filter,
        'score': score_filter,

        'nat64_selected': nat64_selected,
        'ipv6_selected': ipv6_selected,
        'poor_selected': poor_selected,
        'good_selected': good_selected,
        'perfect_selected': perfect_selected,

        'measurements': measurements[:50],
    })


def show_measurement(request, measurement_id):
    measurement = get_object_or_404(Measurement, pk=measurement_id)
    return render(request, 'v6score/measurement.html', {
        'measurement': measurement,
        'url': measurement.url,
    })
