"""Access policy for API documentation; uses the shop's existing admin role."""

from rest_framework.permissions import BasePermission


class IsShopAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated
            and request.user.role == 'admin'
        )
