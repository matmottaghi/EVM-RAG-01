from rest_framework.authentication import SessionAuthentication


class CsrfEnforcedSessionAuthentication(SessionAuthentication):
    """Apply CSRF validation to unsafe API requests, including anonymous ones."""

    def authenticate(self, request):
        self.enforce_csrf(request)
        user = getattr(request._request, "user", None)
        if user is not None and user.is_authenticated:
            return user, None
        return None
