from rest_framework_simplejwt.authentication import JWTAuthentication


class AuditJWTAuthentication(JWTAuthentication):

    def authenticate(self, request):
        if not request.META.get('HTTP_AUTHORIZATION'):
            token = request.COOKIES.get('auth_token')

            if token:
                request.META['HTTP_AUTHORIZATION'] = f'Bearer {token}'

        result = super().authenticate(request)

        # Далее идёт твой существующий код
        # обработки result и журналирования

        if result is not None:
            user, token = result

            impersonator_id = token.get('impersonator_id')

            if impersonator_id is not None:
                # request._request — исходный Django HttpRequest.
                request._request.impersonation_audit = {
                    'admin_id': impersonator_id,
                    'target_user_id': user.pk,
                }

        return result