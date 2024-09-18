# may be executed on old python versions? (should not, but keep compat for a while more)
# type: ignore  # Ignore all type checking
from __future__ import unicode_literals

import sys
import os
import errno
import pwd

def logError(err):
    print(err)


def updateAuthorizedKeys(user, pubKey):
    # No X2Go server on windows
    if 'win' in sys.platform:
        logError('Not a linux platform')
        return

    userInfo = pwd.getpwnam(user)

    # Create .ssh on user home
    home = userInfo.pw_dir.rstrip('/')

    if not os.path.exists(home):  # User not found, nothing done
        logError('Home folder for user {} not found'.format(user))
        return

    uid = userInfo.pw_uid

    sshFolder = '{}/.ssh'.format(home)
    if not os.path.exists(sshFolder):
        try:
            os.makedirs(sshFolder, 0o700)
            os.chown(sshFolder, uid, -1)
        except OSError as e:
            if e.errno != errno.EEXIST:
                logError('Error creating .ssh folder for user {}: {}'.format(user, e))
                return
            # Folder has been created in between test & creation, thats ok

    authorizedKeys = '{}/authorized_keys'.format(sshFolder)
    try:
        with open(authorizedKeys, 'r') as f:
            lines = f.readlines()
    except Exception:
        lines = []

    with open(authorizedKeys, 'w') as f:
        for line in lines:
            if 'UDS@X2GOCLIENT' not in line and line.strip():
                f.write(line)
        # Append pubkey
        f.write('ssh-rsa {} UDS@X2GOCLIENT\n'.format(pubKey))

    # Ensure access is correct
    os.chown(authorizedKeys, uid, -1)
    os.chmod(authorizedKeys, 0o600)

    # Done


# __USER__ and __KEY__ will be replaced by the real values, they are placeholders (and must be left as is)
updateAuthorizedKeys('__USER__', '__KEY__')
