from django.conf.urls import url

from v6score import views

urlpatterns = [
    url(r'^$', views.show_overview, name='overview'),
    url(r'^measurement-(\d+)/$', views.show_measurement, name='measurement'),
    url(r'^measurement-(\d+)/raw/(v4only|v6only|nat64)/$', views.show_measurement_data, name='measurement_data'),
    url(r'^measurement-(\d+)/debug/(v4only|v6only|nat64)/$', views.show_measurement_debug, name='measurement_debug'),
]
