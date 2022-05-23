# -*- coding: utf-8 -*-
"""
Url patterns for UDS project (Django)
"""
from django.urls import include, path

urlpatterns = [
    path('', include('uds.urls')),
]
