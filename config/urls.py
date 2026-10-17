"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse
from django.conf import settings
from django.views.static import serve
from django.urls import re_path


def home(request):
    """Временная заглушка для главной страницы."""
    return HttpResponse(
        '<h1>Shop API</h1>'
        '<p>API интернет-магазина работает.</p>'
        '<p><a href="/api/status/">Проверить состояние API</a></p>'
    )


urlpatterns = [
    # Временная главная страница
    path('', home, name='home'),

    # Панель администратора Django
    path('admin/', admin.site.urls),

    # Маршруты API интернет-магазина
    path('api/', include('api.urls')),
]


# Раздача изображений товаров в режиме разработки
if settings.DEBUG:
    urlpatterns += [
        re_path(
            r'^images/(?P<path>.*)$',
            serve,
            {'document_root': settings.BASE_DIR / 'wwwroot' / 'images'}
        ),
    ]