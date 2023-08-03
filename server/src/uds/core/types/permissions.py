from django.utils.translation import gettext as _


import enum


class PermissionType(enum.IntEnum):
    NONE = 0
    READ = 32
    MANAGEMENT = 64
    ALL = 96

    def as_str(self) -> str:
        """Returns the permission as a string"""
        return {
            PermissionType.NONE: _('None'),
            PermissionType.READ: _('Read'),
            PermissionType.MANAGEMENT: _('Manage'),
            PermissionType.ALL: _('All'),
        }.get(self, _('None'))

    @staticmethod
    def from_str(value: str) -> 'PermissionType':
        """Returns the permission from a string"""
        value = value.lower()
        if value in ('0', 'none'):
            return PermissionType.NONE
        if value in ('1', 'read'):
            return PermissionType.READ
        if value in ('2', 'manage', 'management'):
            return PermissionType.MANAGEMENT
        if value in ('3', 'all', 'rw', 'readwrite', 'read/write'):
            return PermissionType.ALL
        # Unknown value, return NONE
        return PermissionType.NONE

    def includes(self, permission: 'PermissionType') -> bool:
        """Returns if the permission includes the given permission"""
        return self.value >= permission.value
