from __future__ import unicode_literals
import logging

logger = logging.getLogger(__name__)


class XUACompatibleMiddleware(object):
    """
    Add a X-UA-Compatible header to the response
    This header tells to Internet Explorer to render page with latest
    possible version or to use chrome frame if it is installed.
    """
    def process_response(self, request, response):
        if response.get('content-type', '').startswith('text/html'):
            response['X-UA-Compatible'] = 'IE=edge'
        return response
