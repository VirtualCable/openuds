# -*- coding: utf-8 -*-

#
# Copyright (c) 2012 Virtual Cable S.L.
# All rights reserved.
#

'''
@author: Adolfo Gómez, dkmaster at dkmon dot com
'''

from django.conf.urls.defaults import patterns, include

urlpatterns = patterns(__package__,
     (r'^pam$', 'views.pam'),
    )
            