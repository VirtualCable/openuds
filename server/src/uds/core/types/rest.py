# -*- coding: utf-8 -*-
#
# Copyright (c) 2023 Virtual Cable S.L.U.
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
import dataclasses
import collections.abc

from click import group

class TypeInfoDict(typing.TypedDict):
    name: str
    type: str
    description: str
    icon: str
    
    group: typing.NotRequired[str]


@dataclasses.dataclass
class TypeInfo:
    name: str
    type: str
    description: str
    icon: str

    def as_dict(self, group: typing.Optional[str] = None) -> TypeInfoDict:
        res: TypeInfoDict = {
            'name': self.name,
            'type': self.type,
            'description': self.description,
            'icon': self.icon,
        }
        if group is not None:
            res['group'] = group
        return res
        
# This is a named tuple for convenience, and must be
# compatible with tuple[str, bool] (name, needs_parent)
class ModelCustomMethod(typing.NamedTuple):
    name: str
    needs_parent: bool = True

# Alias for item type
ItemDictType = dict[str, typing.Any]

# Alias for get_items return type
ManyItemsDictType = typing.Union[list[ItemDictType], ItemDictType]