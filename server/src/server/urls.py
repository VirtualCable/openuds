# -*- coding: utf-8 -*-
'''
Url patterns for UDS project (Django)
'''
from django.conf.urls import patterns, include

# Uncomment the next two lines to enable the admin:
# from django.contrib import admin
# admin.autodiscover()

urlpatterns = patterns('',
    (r'^', include('uds.urls'))
)
