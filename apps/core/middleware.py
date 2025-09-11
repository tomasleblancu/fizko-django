from django.utils import timezone
from django.http import Http404


class TimezoneMiddleware:
    """
    Middleware para manejar timezone
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Activar timezone de Santiago por defecto
        timezone.activate(timezone.get_current_timezone())
        response = self.get_response(request)
        return response


class CompanyMiddleware:
    """
    Middleware para manejar contexto de empresa
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Obtener company_id del header
        company_id = request.headers.get('X-Company-ID')
        if company_id:
            request.company_id = company_id
        
        response = self.get_response(request)
        return response