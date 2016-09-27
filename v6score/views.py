from datetime import timedelta

from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

from v6score.models import Measurement, Website, is_valid_hostname


def show_overview(request):
    measurements = Measurement.objects.all() \
                       .exclude(finished=None) \
                       .exclude(v6only_score=None, nat64_score=None) \
                       .order_by('-finished')[:25]
    return render(request, 'v6score/overview.html', {
        'measurements': measurements,
    })


def show_measurement(request, measurement_id):
    measurement = get_object_or_404(Measurement, pk=measurement_id)
    return render(request, 'v6score/measurement.html', {
        'measurement': measurement,
    })


@require_POST
def request_measurement(request):
    hostname = request.POST['hostname'].strip()
    if not is_valid_hostname(hostname):
        messages.add_message(request, messages.ERROR, "{} is not a valid hostname".format(hostname))
        return redirect('overview')

    website = Website.objects.get_or_create(hostname=hostname)[0]

    measurement = website.measurement_set.filter(finished=None).order_by('requested').first()
    if measurement:
        if not measurement.manual:
            # Mark as manual
            measurement.manual = True
            measurement.save()
    else:
        recent = timezone.now() - timedelta(minutes=10)
        measurement = website.measurement_set.filter(finished__gt=recent).order_by('-finished').first()
        if not measurement:
            measurement = Measurement(website=website, manual=True)
            measurement.save()

    return redirect(measurement)
