from django.conf.urls import url

from v6score import views

urlpatterns = [
    url(r'^$', views.show_overview, name='overview'),
    url(r'^measurement-(\d+)/$', views.show_measurement, name='measurement'),
]
