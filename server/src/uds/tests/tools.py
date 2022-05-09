import logging
import typing

from django.test.client import Client
from django.conf import settings

from uds.core.managers.crypto import CryptoManager


def getClient() -> Client:
    # Ensure enterprise middleware is not enabled if it exists...
    settings.MIDDLEWARE = [
        'django.contrib.sessions.middleware.SessionMiddleware',
        'django.middleware.locale.LocaleMiddleware',
        'django.middleware.common.CommonMiddleware',
        'django.middleware.csrf.CsrfViewMiddleware',
        'django.contrib.messages.middleware.MessageMiddleware',
        'uds.core.util.middleware.request.GlobalRequestMiddleware',
    ]

    client = Client()
    client.cookies['uds'] = CryptoManager().randomString(48)

    # Patch the client to include 
    #             HTTP_USER_AGENT='Testing user agent', 
    # GET, POST, PUT, DELETE methods
    _oldRequest = client.request

    def _request(**kwargs):
        if 'HTTP_USER_AGENT' not in kwargs:
            kwargs['HTTP_USER_AGENT'] = 'Testing user agent'
        return _oldRequest(**kwargs)  # type: ignore

    client.request = _request
    
    return client