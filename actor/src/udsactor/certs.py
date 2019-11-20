# -*- coding: utf-8 -*-
#
# Copyright (c) 2014 Virtual Cable S.L.
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
#    * Neither the name of Virtual Cable S.L. nor the names of its contributors
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

'''
@author: Adolfo Gómez, dkmaster at dkmon dot com
'''

from tempfile import gettempdir
from os.path import exists, join

CERTFILE = 'UDSActor.pem'


def createSelfSignedCert(force=False):

    certFile = join(gettempdir(), CERTFILE)

    if exists(certFile) and not force:
        return certFile

    certData = '''-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQCb50K3mIznNklz
yVAD7xSQOSJQ6+NPXj7U9/4zLZ+TvmbQ7RqUUsxbfxHbeRnoYTWV2nKk4+tHqmvz
ujLSS/loFhTSMqtrLn7rowSYJoQhKOUkAiQlWkqCfItWgL5pJopDpNHFul9Rn3ds
PMWQTiGeUNR4Y3RnBhr1Q1BsqAzf4m6zFUmgLPPmVLdF4uJ3Tuz8TSy2gWLs5aSr
5do4WamwUfYjRSVMJECmwjUM4rQ8SQgg0sHBeBuDUGNBvBQFac1G7qUcMReeu8Zr
DUtMsXma/l4rA8NB5CRmTrQbTBF4l+jb2BDFebDqDUK1Oqs9X35yOQfDOAFYHiix
PX0IsXOZAgMBAAECggEBAJi3000RrIUZUp6Ph0gzPMuCjDEEwWiQA7CPNX1gpb8O
dp0WhkDhUroWIaICYPSXtOwUTtVjRqivMoxPy1Thg3EIoGC/rdeSdlXRHMEGicwJ
yVyalFnatr5Xzg5wkxVh4XMd0zeDt7e3JD7s0QLo5lm1CEzd77qz6lhzFic5/1KX
bzdULtTlq60dazg2hEbcS4OmM1UMCtRVDAsOIUIZPL0M9j1C1d1iEdYnh2xshKeG
/GOfo95xsgdMlGjtv3hUT5ryKVoEsu+36rGb4VfhPfUvvoVbRx5QZpW+QvxaYh5E
Fi0JEROozFwG31Y++8El7J3yQko8cFBa1lYYUwwpNAECgYEAykT+GiM2YxJ4uVF1
OoKiE9BD53i0IG5j87lGPnWqzEwYBwnqjEKDTou+uzMGz3MDV56UEFNho7wUWh28
LpEkjJB9QgbsugjxIBr4JoL/rYk036e/6+U8I95lvYWrzb+rBMIkRDYI7kbQD/mQ
piYUpuCkTymNAu2RisK6bBzJslkCgYEAxVE23OQvkCeOV8hJNPZGpJ1mDS+TiOow
oOScMZmZpail181eYbAfMsCr7ri812lSj98NvA2GNVLpddil6LtS1cQ5p36lFBtV
xQUMZiFz4qVbEak+izL+vPaev/mXXsOcibAIQ+qI/0txFpNhJjpaaSy6vRCBYFmc
8pgSoBnBI0ECgYAUKCn2atnpp5aWSTLYgNosBU4vDA1PShD14dnJMaqyr0aZtPhF
v/8b3btFJoGgPMLxgWEZ+2U4ju6sSFhPf7FXvLJu2QfQRkHZRDbEh7t5DLpTK4Fp
va9vl6Ml7uM/HsGpOLuqfIQJUs87OFCc7iCSvMJDDU37I7ekT2GKkpfbCQKBgBrE
0NeY0WcSJrp7/oqD2sOcYurpCG/rrZs2SIZmGzUhMxaa0vIXzbO59dlWELB8pmnE
Tf20K//x9qA5OxDe0PcVPukdQlH+/1zSOYNliG44FqnHtyd1TJ/gKVtMBiAiE4uO
aSClod5Yosf4SJbCFd/s5Iyfv52NqsAyp1w3Aj/BAoGAVCnEiGUfyHlIR+UH4zZW
GXJMeqdZLfcEIszMxLePkml4gUQhoq9oIs/Kw+L1DDxUwzkXN4BNTlFbOSu9gzK1
dhuIUGfS6RPL88U+ivC3A0y2jT43oUMqe3hiRt360UQ1GXzp2dMnR9odSRB1wHoO
IOjEBZ8341/c9ZHc5PCGAG8=
-----END PRIVATE KEY-----
-----BEGIN CERTIFICATE-----
MIID7zCCAtegAwIBAgIJAIrEIthCfxUCMA0GCSqGSIb3DQEBCwUAMIGNMQswCQYD
VQQGEwJFUzEPMA0GA1UECAwGTWFkcmlkMREwDwYDVQQHDAhBbGNvcmNvbjEMMAoG
A1UECgwDVURTMQ4wDAYDVQQLDAVBY3RvcjESMBAGA1UEAwwJVURTIEFjdG9yMSgw
JgYJKoZIhvcNAQkBFhlzdXBwb3J0QHVkc2VudGVycHJpc2UuY29tMB4XDTE0MTAy
NjIzNDEyNFoXDTI0MTAyMzIzNDEyNFowgY0xCzAJBgNVBAYTAkVTMQ8wDQYDVQQI
DAZNYWRyaWQxETAPBgNVBAcMCEFsY29yY29uMQwwCgYDVQQKDANVRFMxDjAMBgNV
BAsMBUFjdG9yMRIwEAYDVQQDDAlVRFMgQWN0b3IxKDAmBgkqhkiG9w0BCQEWGXN1
cHBvcnRAdWRzZW50ZXJwcmlzZS5jb20wggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAw
ggEKAoIBAQCb50K3mIznNklzyVAD7xSQOSJQ6+NPXj7U9/4zLZ+TvmbQ7RqUUsxb
fxHbeRnoYTWV2nKk4+tHqmvzujLSS/loFhTSMqtrLn7rowSYJoQhKOUkAiQlWkqC
fItWgL5pJopDpNHFul9Rn3dsPMWQTiGeUNR4Y3RnBhr1Q1BsqAzf4m6zFUmgLPPm
VLdF4uJ3Tuz8TSy2gWLs5aSr5do4WamwUfYjRSVMJECmwjUM4rQ8SQgg0sHBeBuD
UGNBvBQFac1G7qUcMReeu8ZrDUtMsXma/l4rA8NB5CRmTrQbTBF4l+jb2BDFebDq
DUK1Oqs9X35yOQfDOAFYHiixPX0IsXOZAgMBAAGjUDBOMB0GA1UdDgQWBBRShS90
5lJTNvYPIEqP3GxWwG5iiDAfBgNVHSMEGDAWgBRShS905lJTNvYPIEqP3GxWwG5i
iDAMBgNVHRMEBTADAQH/MA0GCSqGSIb3DQEBCwUAA4IBAQAU0Sp4gXhQmRVzq+7+
vRFUkQuPj4Ga/d9r5Wrbg3hck3+5pwe9/7APoq0P/M0DBhQpiJKjrD6ydUevC+Y/
43ZOJPhMlNw0o6TdQxOkX6FDwQanLLs7sfvJvqtVzYn3nuRFKT3dvl7Zg44QMw2M
ay42q59fAcpB4LaDx/i7gOYSS5eca3lYW7j7YSr/+ozXK2KlgUkuCUHN95lOq+dF
trmV9mjzM4CNPZqKSE7kpHRywgrXGPCO000NvEGSYf82AtgRSFKiU8NWLQSEPdcB
k//2dsQZw2cRZ8DrC2B6Tb3M+3+CA6wVyqfqZh1SZva3LfGvq/C+u+ItguzPqNpI
xtvM
-----END CERTIFICATE-----'''
    with open(certFile, "wt") as f:
        f.write(certData)

    return certFile
