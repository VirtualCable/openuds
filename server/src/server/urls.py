# -*- coding: utf-8 -*-
'''
Url patterns for UDS project (Django)
'''
from django.conf.urls import include, url

# Uncomment the next two lines to enable the admin:
# from django.contrib import admin
# admin.autodiscover()


urlpatterns = [
    url(r'^', include('uds.urls')),
]
