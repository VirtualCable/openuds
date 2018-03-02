# -*- coding: utf-8 -*-
"""
Url patterns for UDS project (Django)
"""
from django.conf.urls import include
from django.urls import path


# Uncomment the next two lines to enable the admin:
# from django.contrib import admin
# admin.autodiscover()


urlpatterns = [
    path('', include('uds.urls')),
]
