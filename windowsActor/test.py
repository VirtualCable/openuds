from __future__ import unicode_literals

from management import *
from store import readConfig


cfg = readConfig()
print "Intefaces: ", list(getNetworkInfo())
print "Joined Domain: ", getDomainName()

renameComputer('win7-64')
joinDomain('dom.dkmon.com', 'ou=pruebas_2,dc=dom,dc=dkmon,dc=com', 'administrador@dom.dkmon.com', 'Temporal2012', True)
#reboot()
