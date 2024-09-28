import typing

from django.utils.translation import gettext
from django.templatetags.static import static
from uds.REST.methods.client import CLIENT_VERSION


# all plugins are under url clients...
PLUGINS: typing.Final[list[dict[str, 'str|bool']]] = [
    {
        'url': static('clients/' + url.format(version=CLIENT_VERSION)),
        'description': description,
        'name': name,
        'legacy': legacy,
    }
    for url, description, name, legacy in (
        (
            'UDSClientSetup-{version}.exe',
            gettext('Windows client'),
            'Windows',
            False,
        ),
        ('UDSClient-{version}.pkg', gettext('Mac OS X client'), 'MacOS', False),
        (
            'udsclient3_{version}_all.deb',
            gettext('Debian based Linux client') + ' ' + gettext('(requires Python-3.9 or newer)'),
            'Linux',
            False,
        ),
        (
            'udsclient3-{version}-1.noarch.rpm',
            gettext('RPM based Linux client (Fedora, Suse, ...)')
            + ' '
            + gettext('(requires Python-3.9 or newer)'),
            'Linux',
            False,
        ),
        (
            'udsclient3-x86_64-{version}.tar.gz',
            gettext('Binary appimage X86_64 Linux client'),
            'Linux',
            False,
        ),
        (
            'udsclient3-armhf-{version}.tar.gz',
            gettext('Binary appimage ARMHF Linux client (Raspberry, ...)'),
            'Linux',
            False,
        ),
        (
            'udsclient3-{version}.tar.gz',
            gettext('Generic .tar.gz Linux client') + ' ' + gettext('(requires Python-3.9 or newer)'),
            'Linux',
            False,
        ),
    )
]
