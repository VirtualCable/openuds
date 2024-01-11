# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2023 Virtual Cable S.L.U.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#
#    * Redistributions of source code must retain the above copyright notice,
#      this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above copyright notice,
#      this list of conditions and the following disclaimer in the documentation
#      and/or other materials provided with the distribution.
#    * Neither the name of Virtual Cable S.L.U. nor the names of its contributors
#      may be used to endorse or promote products derived from this software
#      without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import base64
import typing

DEFAULT_IMAGE_BASE64: typing.Final[str] = (
    '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'
    'QDKr3Hhw7z9S0OXPt9WRlwAAAABJRU5ErkJggg=='
)
DEFAULT_IMAGE: typing.Final[bytes] = base64.b64decode(DEFAULT_IMAGE_BASE64)

DEFAULT_THUMB_BASE64: typing.Final[str] = (
    'iVBORw0KGgoAAAANSUhEUgAAAC4AAAAwCAMAAABZu7juAAADAFBMVEUAAAD///8Yf/JCWAhdewW4'
    'yhbV4UsYf/I0a5FCWAhdewW4yhbV4UsYf/JCWAhdewW4yhbV4UsYf/JCWAhdewW4yhbV4UsYf/JC'
    'WAhdewV3kRe4yhbV4UsYf/JCWAhdewW4yhbV4UsYf/JCWAhdewW4yhbV4UsYf/JCWAhdewVmmrG4'
    'yhbV4UsYf/JCWAhdewW4yhbV4UsYf/JCWAhdewW4yhbV4UsYf/JCWAhdewW4yhbL2EbV4UsYf/JC'
    'WAhdewW4yhbV4UsYf/JCWAhdewW4yhbV4UsYf/JCWAhWagpdewWtvxK4yhbV4UsYf/JCWAhdewWz'
    'xRW4yhbV4UsQY8kRZs4Ra9MSZcwSbtgTadEUbNYUb9sVc+EVduYWYr8Wcd4WeesXdOMXeOgXffAY'
    'e+0Yf/IcYrYecMwefOcfYKwiedskX6IlacEmd9AnX5gqdcQrXo4rcrcrfuArg+gtXoMub6oxXXgx'
    'bZ0zXG00a5E0cLg1W2I2aYM4W1Y4ZnU6Wkk7ZGY9Wjs9X0Y9YVc+WS4/XTY/d7BBWR1BWyJCWAhC'
    'frpGjNNKYQhLfqZRkcdTlP9UaApUkvNVj9pVkedWhJ5Wjc5XibRXi8FYiKdahYpahplbcApbgm1b'
    'g3xcfTlcf0xcgV1dewVdfCRdmfZhi5RijZxjgQVkeAplggpmmrFnnexqhgZrfw1rkYtuiRJvn6Vw'
    'iwZwouNyhw10mIJ1jkN2kAp2kBd3pJl5p9l7jQ57lQt9nnd+lhyBmgyClRCGnSCGpG2HnwyInBCJ'
    'rYCKscWNpA2OpCaPq2GQohCStrqTqQ6VqiqXqRCYrg6YsVaZt2SaurCdsC2esBOesw+guEmhvFWi'
    'v6WjtjGjtxOju2mlthOovBOovTyqwESqxJmrvROrvTatwRSwxCuxxTKywxaywzqzxhW4yha4zoO5'
    'yT3Az0DA03XH1kXH2GnO20jO3FrV4Uvx8fHy8vLz8/P09PT19fX29vb39/f4+Pj5+fn6+vr7+/v8'
    '/Pz9/f3+/v7///8+5RGcAAAAVHRSTlMAABAQEBAQICAgICAgMDAwMDBAQEBAQFBQUFBQUGBgYGBg'
    'cHBwcHCAgICAgICPj4+Pj5+fn5+fr6+vr6+vv7+/v7/Pz8/Pz9/f39/f39/v7+/v7+8oPBfEAAAB'
    'TElEQVR4nJ3VPU5DMQwAYCPBAhILF+ASDHTqFUBInCAjZ+j8prAjJHwNJMaOjJzB6zsCTZ6TFztJ'
    'ndZTbX3Jc/5UuDgp4EwOKbYU4mPKwfWaU4rIdrs84q7BqdAvMV5dCP6E4qum90W7HMFLvi84Ke3e'
    'Ko6kfcHD9KoZ7Z2TXi9VeZPjSRzwV8xvcdXOn9CNU5XtkMW1J5P/CB5qPT6HUNPHAdDkOM/e63YW'
    'P023NUfva8+8vsALb3rJgdfpuz69qIJfdvhNmw9MLzgw177L8/Q4wjvtmFz6Li/8t7WRwn/hvtY1'
    'r9qH4/zgsdgdsDj7z8jB5suAMLuudzhcY1P3OMAjPjWqXd6Os/jaZfyl7/lzPoE2TwmBSA1ej7Y4'
    'iXSMr4c7woH/a6+GeYjNWO9lxjyVtpJz6znd8KmmEh3dd8qX4L58OvqRcvpwWOo/oi1qR5RpMLcA'
    'AAAASUVORK5CYII='
)
DEFAULT_THUMB: typing.Final[bytes] = base64.b64decode(DEFAULT_THUMB_BASE64)
