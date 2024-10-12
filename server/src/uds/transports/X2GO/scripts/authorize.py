# may be executed on old python versions? (should not, but keep compat for a while more)
# type: ignore  # Ignore all type checking
from __future__ import unicode_literals

import sys
import os
import errno
import pwd

def log_error(err, username: str = None):
    with open('/tmp/uds-x2go-error-{}.log'.format(username or None), 'a') as f:
        f.write(err)
 
    print(err)


def update_authorized_keys(username, pubKey):
    # No X2Go server on windows
    if 'win' in sys.platform:
        log_error('Not a linux platform')
        return

    user_info = pwd.getpwnam(username)
    user_info.

    # Create .ssh on user home
    home = user_info.pw_dir.rstrip('/')

    if not os.path.exists(home):  # User not found, nothing done
        log_error('Home folder for user {} not found'.format(username))
        return

    uid = user_info.pw_uid

    ssh_folder = '{}/.ssh'.format(home)
    if not os.path.exists(ssh_folder):
        try:
            os.makedirs(ssh_folder, 0o700)
            os.chown(ssh_folder, uid, -1)
        except OSError as e:
            if e.errno != errno.EEXIST:
                log_error('Error creating .ssh folder for user {}: {}'.format(username, e), username)
                return
            # Folder has been created in between test & creation, thats ok

    authorized_keys = '{}/authorized_keys'.format(ssh_folder)
    try:
        with open(authorized_keys, 'r') as f:
            lines = f.readlines()
    except Exception:
        lines = []

    with open(authorized_keys, 'w') as f:
        f.writelines(
            filter(
                lambda x: 'UDS@X2GOCLIENT' not in x and x.strip(),
                lines
            )
        )
        # Append pubkey
        f.write('ssh-rsa {} UDS@X2GOCLIENT\n'.format(pubKey))

    # Ensure access is correct
    os.chown(authorized_keys, uid, -1)
    os.chmod(authorized_keys, 0o600)

    # Done


# __USER__ and __KEY__ will be replaced by the real values, 
# # they are placeholders for the real values so keep them.
update_authorized_keys('__USER__', '__KEY__')
