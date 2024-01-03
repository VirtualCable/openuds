from uds.core.util.config import Config

# Early declaration of config variables
ORGANIZATION_NAME = Config.section(Config.SectionType.SAML).value('Organization Name', 'UDS', help='Organization name to display on SAML SP Metadata')
ORGANIZATION_DISPLAY = Config.section(Config.SectionType.SAML).value('Org. Display Name', 'UDS Organization', help='Organization Display name to display on SAML SP Metadata')
ORGANIZATION_URL = Config.section(Config.SectionType.SAML).value('Organization URL', 'http://www.udsenterprise.com', help='Organization url to display on SAML SP Metadata')

ORGANIZATION_NAME.get()
ORGANIZATION_DISPLAY.get()
ORGANIZATION_URL.get()
