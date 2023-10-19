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
import re
import logging

from uds.core import ui, exceptions
from uds.core.util import ensure

logger = logging.getLogger(__name__)

def validateRegexField(field: ui.gui.TextField, fieldValue: typing.Optional[str] = None):
    """
    Validates the multi line fields refering to attributes
    """
    value: str = fieldValue or field.value
    for line in value.splitlines():
        if line.find('=') != -1:
            pattern = line.split('=')[0:2][1]
            if pattern.find('(') == -1:
                pattern = '(' + pattern + ')'
            try:
                re.search(pattern, '')
            except Exception as e:
                raise exceptions.ValidationError(f'Invalid pattern at {field.label}: {line}') from e

def processRegexField(field: str, attributes: typing.Mapping[str, typing.Union[str, typing.List[str]]]) -> typing.List[str]:
    """Proccesses a field, that can be a multiline field, and returns a list of values
    
    Args:
        field (str): Field to process
        attributes (typing.Dict[str, typing.List[str]]): Attributes to use on processing
    """
    try:
        res: typing.List[str] = []

        def getAttr(attrName: str) -> typing.List[str]:
            try:
                val: typing.List[str] = []
                if '+' in attrName:
                    attrList = attrName.split('+')
                    # Check all attributes are present, and has only one value
                    attrValues = [ensure.is_list(attributes.get(a, [''])) for a in attrList]
                    if not all([len(v) <= 1 for v in attrValues]):
                        logger.warning(
                            'Attribute %s do not has exactly one value, skipping %s', attrName, line
                        )
                        return val

                    val = [''.join(v) for v in attrValues]  # flatten
                elif '**' in attrName:
                    # Prepend the value after : to attribute value before :
                    attr, prependable = attrName.split('**')
                    val = [prependable + a for a in ensure.is_list(attributes.get(attr, []))]
                else:
                    val = ensure.is_list(attributes.get(attrName, []))
                return val
            except Exception as e:
                logger.warning('Error processing attribute %s (%s): %s', attrName, attributes, e)
                return []

        for line in field.splitlines():
            equalPos = line.find('=')
            if equalPos != -1:
                attr, pattern = (line[:equalPos], line[equalPos + 1 :])
                # if pattern do not have groups, define one with full re
                if pattern.find('(') == -1:
                    pattern = '(' + pattern + ')'

                val = getAttr(attr)

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
                res += getAttr(line)
            logger.debug('Result: %s', res)
        return res
    except Exception as e:
        logger.warning('Error processing field %s (%s): %s', field, attributes, e)
        return []
