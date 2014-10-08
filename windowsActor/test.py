from __future__ import unicode_literals

from windows_operations import *
from store import readConfig
import REST

cfg = readConfig()
print cfg
print "Intefaces: ", list(getNetworkInfo())
print "Joined Domain: ", getDomainName()

#renameComputer('win7-64')
#joinDomain('dom.dkmon.com', 'ou=pruebas_2,dc=dom,dc=dkmon,dc=com', 'administrador@dom.dkmon.com', 'Temporal2012', True)
#reboot()
r = REST.Api(cfg['host'], cfg['masterKey'], cfg['ssl'], scrambledResponses=True)
r.test()
try:
    r.init('02:46:00:00:00:07')
except REST.UnmanagedHostError:
    print 'Unmanaged host (confirmed)'


uuid = r.init('02:46:00:00:00:06')

print 'uuid = {}'.format(uuid)

#print 'Login: {}'.format(r.login('test-user'))
#print 'Logout: {}'.format(r.logout('test-user'))
print r.information()

print r.setReady([(v.mac, v.ip) for v in getNetworkInfo()])
print r.log(REST.ERROR, 'Test error message')
