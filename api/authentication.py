from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken


class CookieJWTAuthentication(JWTAuthentication):
    """Authenticate ordinary JWTs from the header or auth_token cookie."""

    def authenticate(self, request):
        if not request.META.get('HTTP_AUTHORIZATION'):
            token = request.COOKIES.get('auth_token')
            if token:
                request.META['HTTP_AUTHORIZATION'] = f'Bearer {token}'
        return super().authenticate(request)

    def get_validated_token(self, raw_token):
        token = super().get_validated_token(raw_token)
        if 'impersonator_id' in token:
            raise InvalidToken('Impersonation tokens are no longer supported.')
        return token
