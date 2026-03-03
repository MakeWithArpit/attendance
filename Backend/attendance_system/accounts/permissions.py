"""
accounts/permissions.py
Role-based permission classes
"""
from rest_framework.permissions import BasePermission


class IsAdmin(BasePermission):
    """Only Admin can access"""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'admin'


class IsTeacher(BasePermission):
    """Only Teacher can access"""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'teacher'


class IsStudent(BasePermission):
    """Only Student can access"""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'student'


class IsTeacherOrAdmin(BasePermission):
    """Teacher or Admin can access"""
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.role in ['teacher', 'admin']
        )


class IsAdminOrReadOnly(BasePermission):
    """Admin can write; others can only read"""
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True
        return request.user.role == 'admin'
