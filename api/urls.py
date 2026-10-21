# uv run python manage.py runserver

from django.urls import path
from . import views
from drf_spectacular.views import (
    SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView,
)
from .authentication import CookieJWTAuthentication
from .documentation import IsShopAdmin

documentation_access = {
    'authentication_classes': [CookieJWTAuthentication],
    'permission_classes': [IsShopAdmin],
}

urlpatterns = [
    path('schema/', SpectacularAPIView.as_view(**documentation_access), name='schema'),
    path('docs/', SpectacularSwaggerView.as_view(url_name='schema', **documentation_access), name='swagger-ui'),
    path('redoc/', SpectacularRedocView.as_view(url_name='schema', **documentation_access), name='redoc'),
    # Проверка работоспособности API
    path('status/', views.api_status, name='api-status'),

    # Регистрация и вход пользователя
    path('Auth/register', views.register, name='api-register'),
    path('Auth/login', views.login, name='api-login'),
    path('Auth/me', views.me, name='api-me'),
    path('Auth/logout', views.logout, name='api-logout'),

    # Управление пользователями
    path('Users', views.users_list, name='users-list'),
    path('Users/<int:user_id>', views.user_detail, name='user-detail'),
    path('Users', views.user_create, name='user-create'),
    
    # Список пользователей и создание пользователя
    path('Users', views.users_list, name='api-users'),

    # Получение отдельного пользователя
    path('Users/<int:user_id>', views.user_detail, name='api-user-detail'),
    
    # Категории товаров
    path('Category', views.category_list, name='category-list'),
    path('Category/<int:category_id>', views.category_detail, name='category-detail'),
    # Товары
    path('Product', views.product_list, name='product-list'),
    path('Product/<int:product_id>', views.product_detail, name='product-detail'),
    path(
    'Products/DeleteImage',
    views.product_delete_image,
    name='product-delete-image'),
    path(
    'Products/LoadImage',
    views.product_load_image,
    name='product-load-image'),
    path(
    'OrderHead/<int:order_id>',
    views.order_head_detail,
    name='order-head-detail'),
    path(
    'OrderHead',
    views.order_head_list,
    name='order-head-list'),
    path(
    'OrderDetail/<int:order_id>',
    views.order_detail_by_id,
    name='order-detail-by-id'),
    path('OrderDetail', views.order_detail_save, name='order-detail-save'),
]


