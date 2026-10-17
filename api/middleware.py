from .models import ImpersonationActionLog


class ImpersonationAuditMiddleware:
    """
    Записывает API-запросы, выполненные
    с использованием токена имперсонации.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Сначала выполняем запрос.
        response = self.get_response(request)

        # Проверяем, была ли имперсонация.
        audit = getattr(request, 'impersonation_audit', None)

        if audit is not None:
            ImpersonationActionLog.objects.create(
                admin_id=audit['admin_id'],
                target_user_id=audit['target_user_id'],
                method=request.method,
                path=request.path,
                status_code=response.status_code,
            )

        return response