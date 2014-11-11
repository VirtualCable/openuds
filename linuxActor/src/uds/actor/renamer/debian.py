# -*- coding: utf-8 -*-
'''
Created on Nov 17, 2011

@author: dkmaster
'''

from . import renamers
import logging, os

logger = logging.getLogger(__name__)


def rename(newName):
    # If new name has "'\t'
    if '\t' in newName:
        newName, account, password = newName.split('\t')
    else:
        account = password = None

    logger.debug('Debian renamer')

    if account is not None:
        os.system('echo "{1}\n{1}" | /usr/bin/passwd {0} 2> /dev/null'.format(account, password))

    f = open('/etc/hostname', 'w')
    f.write(newName)
    f.close()
    os.system('/bin/hostname %s' % newName)

    # add name to "hosts"
    f = open('/etc/hosts', 'r')
    lines = f.readlines()
    f.close()
    f = open('/etc/hosts', 'w')
    f.write("127.0.1.1\t%s\n" % newName)
    for l in lines:
        if l[:9] == '127.0.1.1':
            continue
        f.write(l)
    f.close()

    return True
# All names in lower case
renamers['debian'] = rename
renamers['ubuntu'] = rename
