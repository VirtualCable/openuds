# -*- coding: utf-8 -*-
#
# Copyright (c) 2022 Virtual Cable S.L.U.
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
#    * Neither the name of Virtual Cable S.L.U. nor the names of its contributors
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

"""
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import typing
import collections.abc
import re
import logging

from uds.core import ui, exceptions
from uds.core.util import ensure

logger = logging.getLogger(__name__)


def validate_regex_field(field: ui.gui.TextField, field_value: typing.Optional[str] = None) -> None:
    """
    Validates the multi line fields refering to attributes
    """
    value: str = field_value or field.value
    if value.strip() == '':
        return  # Ok, empty

    for line in value.splitlines():
        if line.find('=') != -1:
            pattern = line.split('=')[0:2][1]
            if pattern.find('(') == -1:
                pattern = '(' + pattern + ')'
            try:
                re.search(pattern, '')
            except Exception as e:
                raise exceptions.ui.ValidationError(f'Invalid pattern at {field.label}: {line}') from e


def get_attributes_regex_field(field: 'ui.gui.TextField|str') -> set[str]:
    """
    Returns a dict of attributes from a multiline field
    """
    content: str = (field.value if isinstance(field, ui.gui.TextField) else field).strip()

    if content == '':
        return set()

    res: set[str] = set()
    for line in content.splitlines():
        attr, _pattern = (line.split('=')[0:2] + [''])[0:2]

        # If attributes concateated with +, add all
        if '+' in attr:
            res.update(attr.split('+'))
        elif ':' in attr:  # lower precedence than +
            res.add(attr.split(':')[0])
        else:  # If not, add the attribute
            res.add(attr)

    return res


def process_regex_field(
    field: str, attributes: collections.abc.Mapping[str, typing.Union[str, list[str]]]
) -> list[str]:
    """Proccesses a field, that can be a multiline field, and returns a list of values

    Args:
        field (str): Field to process
        attributes (dict[str, list[str]]): Attributes to use on processing
    """
    try:
        res: list[str] = []
        field = field.strip()
        if field == '':
            return res

        def _get_attr(attr_name: str) -> list[str]:
            try:
                val: list[str] = []
                if '+' in attr_name:
                    attrs_list = attr_name.split('+')
                    # Check all attributes are present, and has only one value
                    attrs_values = [ensure.as_list(attributes.get(a, [''])) for a in attrs_list]
                    if not all([len(v) <= 1 for v in attrs_values]):
                        logger.warning(
                            'Attribute %s do not has exactly one value, skipping %s', attr_name, line
                        )
                        return val

                    val = [''.join(v) for v in attrs_values]  # flatten
                elif '**' in attr_name:
                    # Prepend the value after : to attribute value before :
                    attr, prependable = attr_name.split('**')
                    val = [prependable + a for a in ensure.as_list(attributes.get(attr, []))]
                else:
                    val = ensure.as_list(attributes.get(attr_name, []))
                return val
            except Exception as e:
                logger.warning('Error processing attribute %s (%s): %s', attr_name, attributes, e)
                return []

        for line in field.splitlines():
            equalPos = line.find('=')
            if equalPos != -1:
                attr, pattern = (line[:equalPos], line[equalPos + 1 :])
                # if pattern do not have groups, define one with full re
                if pattern.find('(') == -1:
                    pattern = '(' + pattern + ')'

                val = _get_attr(attr)

                for v in val:
                    try:
                        logger.debug('Pattern: %s on value %s', pattern, v)
                        srch = re.search(pattern, v)
                        if srch is None:
                            continue
                        res.append(''.join(srch.groups()))
                    except Exception as e:
                        logger.warning('Invalid regular expression')
                        logger.debug(e)
                        break
            else:
                res += _get_attr(line)
            logger.debug('Result: %s', res)
        return res
    except Exception as e:
        logger.warning('Error processing field %s (%s): %s', field, attributes, e)
        return []
