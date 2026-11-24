# -*- coding: utf-8 -*-
from tests.utils.test import UDSTestCase


class TestProcessRegexField(UDSTestCase):
    def test_plain_attr(self) -> None:
        from uds.core.util.auth import process_regex_field
        self.assertEqual(
            process_regex_field('group', {'group': ['a', 'b']}),
            ['a', 'b'],
        )

    def test_plus_concat(self) -> None:
        from uds.core.util.auth import process_regex_field
        # ponytail: current "+" returns one entry per attribute, not a true concat.
        # Fixing that is out of scope for this bug.
        self.assertEqual(
            process_regex_field('a+b', {'a': ['x'], 'b': ['y']}),
            ['x', 'y'],
        )

    def test_colon_prefix_rename(self) -> None:
        from uds.core.util.auth import process_regex_field
        # UCA case: alumno:alumno with attribute value "S" must produce "alumnoS"
        self.assertEqual(
            process_regex_field('alumno:alumno\npas:pas\npdi:pdi',
                                {'alumno': ['S'], 'pas': ['S'], 'pdi': ['N']}),
            ['alumnoS', 'pasS', 'pdiN'],
        )

    def test_colon_self_rename(self) -> None:
        from uds.core.util.auth import process_regex_field
        # grupo2:grupo2 — value of "grupo2" prefixed with "grupo2"
        self.assertEqual(
            process_regex_field('grupo2:grupo2', {'grupo2': ['foo']}),
            ['grupo2foo'],
        )

    def test_double_star_prefix(self) -> None:
        from uds.core.util.auth import process_regex_field
        # Pre-existing ** syntax still works
        self.assertEqual(
            process_regex_field('val**pre', {'val': ['S']}),
            ['preS'],
        )

    def test_regex_with_groups(self) -> None:
        from uds.core.util.auth import process_regex_field
        self.assertEqual(
            process_regex_field('dn=ou=([^,]+)', {'dn': ['ou=staff,dc=uca']}),
            ['staff'],
        )

    def test_get_attributes_regex_field_colon(self) -> None:
        from uds.core.util.auth import get_attributes_regex_field
        # For LDAP: must request the *actual* attribute (right of :), not the prefix
        self.assertEqual(get_attributes_regex_field('alumno:alumno\npas:pas'),
                         {'alumno', 'pas'})

    def test_attribute_name_with_colon_is_used_verbatim(self) -> None:
        from uds.core.util.auth import process_regex_field

        attributes = {
            'urn:oid:1.3.6.1.4.1.5923.1.5.1.1': ['staff'],
            'http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress': ['user@example.com'],
        }
        self.assertEqual(
            process_regex_field('urn:oid:1.3.6.1.4.1.5923.1.5.1.1', attributes),
            ['staff'],
        )
        self.assertEqual(
            process_regex_field(
                'http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress=(.*)@', attributes
            ),
            ['user'],
        )
