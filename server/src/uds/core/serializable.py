# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2021 Virtual Cable S.L.U.
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
import base64
import abc


class Serializable(abc.ABC):
    """
    This class represents the interface that all serializable objects must provide.

    Every single serializable class must implement marshal & unmarshal methods. Also, the class must allow
    to be initialized without parameters, so we can:
    - Initialize the object with default values
    - Read values from seralized data
    """

    _needs_upgrade: bool

    # Note:
    #   We can include a "data" member variable in the class
    #   If found, and has __dict__, then we will use it
    #   on marshal and unmarshal methods

    def __init__(self) -> None:
        self._needs_upgrade = False

    @abc.abstractmethod
    def marshal(self) -> bytes:
        """
        This is the method that must be overriden in order to serialize an object.

        The system will use in fact 'seralize' and 'deserialize' methods, but theese are
        only suitable methods to "codify" serialized values

        :note: This method can be overriden.
        """
        # Default implementation will look for a member variable called "data"
        # This is an struct, and will be pickled by default
        ...

    @abc.abstractmethod
    def unmarshal(self, data: bytes) -> None:
        """
        This is the method that must be overriden in order to deserialize an object.

        The system will use in fact 'seralize' and 'deserialize' methods, but these are
        only convenients methods to "codify" serialized values.

        Take into account that _str can be '' (empty string), but hopefully it will never be none.
        In that case, initialize the object with default values

        Args:
            data : String readed from persistent storage to deseralilize

        :note: This method can be overriden.
        """
        ...

    def serialize(self) -> str:
        """
        Serializes and "obfuscates' the data.
        """
        return base64.b64encode(self.marshal()).decode()

    def deserialize(self, data: str) -> None:
        """
        des-obfuscates the data and then de-serializes it via unmarshal method
        """
        if not data:
            return  # Nothing to do
        self.unmarshal(base64.b64decode(data))

    # For remarshalling purposes
    # These facilitates a faster migration of old data formats to new ones
    # alowing us to remove old format support as soon as possible
    def mark_for_upgrade(self, value: bool = True) -> None:
        """
        Flags this object for remarshalling

        Args:
            value: True if this object needs remarshalling, False if not

        Note:
            This is not mandatory, meaning this that even if flagged, the object
            will not be remarshalled if not appropriate (basically, it's remarshalled on
            get_instance unserialize method call)
        """
        self._needs_upgrade = value

    def needs_upgrade(self) -> bool:
        """
        Returns true if this object needs remarshalling
        """
        return self._needs_upgrade

    def is_dirty(self) -> bool:
        """
        Returns true if this object needs remarshalling
        """
        return True
