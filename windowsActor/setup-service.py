from distutils.core import setup
import py2exe, sys

sys.argv.append('py2exe')

class Target:
    
    def __init__(self, **kw):
        self.__dict__.update(kw)
        # for the versioninfo resources
        self.version = "1.6.0"
        self.name = 'UDSActorService'
        self.description = 'UDS Actor Service for managing UDS Broker controlled machines'
        self.author = 'VirtualCable S.L.U.'
        self.url = 'http://www.udsenterprise.com'
        self.company_name = "VirtualCable S.L.U."
        self.copyright = "(c) 2014 VirtualCable S.L.U."
        self.name = "UDS Actor"


myservice = Target(
    description = 'UDS Actor Service for managing machine from UDS Broker',
    modules = ['UDSActorService'],
    cmdline_style='pywin32'
)

setup(
    options = {"py2exe": {"compressed": 1, "bundle_files": 1} },
    console=["UDSActorService.py"],
    zipfile = None,
    service=[myservice]
)