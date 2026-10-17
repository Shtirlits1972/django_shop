
import token

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import request, status
from rest_framework_simplejwt.tokens import AccessToken
from datetime import date, timedelta, datetime
from .models import User, ImpersonationLog
from .models import Category
from .serializers import CategorySerializer
from .serializers import (
    RegisterSerializer,
    LoginSerializer,
    UserDataSerializer,
    UserCreateSerializer,
    UserUpdateSerializer,
    PASSWORD_MASK,
)
from .models import Product
from .serializers import ProductSerializer
from pathlib import Path
from django.conf import settings
from uuid import uuid4
from django.utils import timezone
from api.models import OrderHead, OrderDetail, OrderHeadView

@api_view(['GET'])
def api_status(request):
    """Возвращает статус API интернет-магазина."""
    return Response({
        'status': 'ok',
        'message': 'API интернет-магазина работает',
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    """Регистрирует пользователя и возвращает JWT-токен."""
    serializer = RegisterSerializer(data=request.data)

    if not serializer.is_valid():
        # Сохраняем привычный для старого API формат ошибки.
        if 'email' in serializer.errors:
            email_errors = serializer.errors['email']
            if any(
                'уже существует' in str(error).lower()
                for error in email_errors
            ):
                return Response(
                    {'message': 'Пользователь с таким email уже существует'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        return Response(
            {'message': 'Проверьте правильность введённых данных',
             'errors': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    data = serializer.validated_data

    # Создаём пользователя с ролью user и подтверждённым аккаунтом.
    user = User.objects.create_user(
        email=data['email'],
        password=data['password'],
        users_name=data.get('usersName', ''),
        role='user',
        is_appruved=True,
    )

    # Добавляем в токен claims, которые ожидает Vue-клиент.
    token = AccessToken.for_user(user)
    token['id'] = user.pk
    token['email'] = user.email
    token['role'] = user.role
    token['name'] = user.users_name
    token['displayName'] = user.users_name

    # Vue ожидает непосредственно строку JWT, а не объект с полем token.
    response = Response(str(token), status=status.HTTP_200_OK)

    # Поддерживаем и cookie старого API.
    response.set_cookie(
        key='auth_token',
        value=str(token),
        httponly=True,
        secure=False,  # Для локальной разработки по HTTP.
        samesite='Lax',
        path='/',
        max_age=30 * 24 * 60 * 60,
    )

    return response


@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    """Проверяет учётные данные и возвращает JWT-токен."""
    serializer = LoginSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(
            {
                'message': 'Проверьте правильность введённых данных',
                'errors': serializer.errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    data = serializer.validated_data

    # Ищем пользователя без учёта регистра email.
    user = User.objects.filter(
        email__iexact=data['email']
    ).first()

    # Проверяем пароль и доступность аккаунта.
    if (
        user is None
        or not user.check_password(data['password'])
        or not user.is_appruved
        or not user.is_active
    ):
        return Response(
            {
                'message': (
                    'Неверные учетные данные или аккаунт не активирован'
                )
            },
            status=status.HTTP_401_UNAUTHORIZED,
        )

    # Создаём JWT с claims, которые ожидает Vue-клиент.
    token = AccessToken.for_user(user)
    token['id'] = user.pk
    token['email'] = user.email
    token['role'] = user.role
    token['name'] = user.users_name
    token['displayName'] = user.users_name

    # Возвращаем токен в формате, ожидаемом существующим Vue-клиентом.
    response = Response(str(token), status=status.HTTP_200_OK)

    # Сохраняем совместимость с cookie старого API.
    response.set_cookie(
        key='auth_token',
        value=str(token),
        httponly=True,
        secure=False,  # Только для локальной разработки по HTTP.
        samesite='Lax',
        path='/',
        max_age=30 * 24 * 60 * 60,
    )

    return response


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me(request):
    """Возвращает данные текущего авторизованного пользователя."""
    user = request.user

    return Response({
        'id': user.pk,
        'email': user.email,
        'role': user.role,
        'usersName': user.users_name,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout(request):
    """Удаляет cookie авторизации и завершает сеанс на клиенте."""
    response = Response({
        'message': 'Вы успешно вышли из системы',
    })

    # Удаляем cookie с тем же именем и путём, что при входе.
    response.delete_cookie(
        key='auth_token',
        path='/',
        samesite='Lax',
    )

    return response


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def users_list(request):
    """Возвращает список пользователей администраторам."""
    if request.user.role != 'admin':
        return Response(
            {'message': 'Недостаточно прав'},
            status=status.HTTP_403_FORBIDDEN,
        )

    users = User.objects.order_by('id')
    serializer = UserDataSerializer(users, many=True)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def user_create(request):
    """Создаёт пользователя администратором."""
    if request.user.role != 'admin':
        return Response(
            {'message': 'Недостаточно прав'},
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = UserCreateSerializer(data=request.data)
    if not serializer.is_valid():
        if 'email' in serializer.errors and any(
            'уже существует' in str(error).lower()
            for error in serializer.errors['email']
        ):
            return Response(
                {'message': 'Пользователь с таким email уже существует'},
                status=status.HTTP_409_CONFLICT,
            )

        return Response(
            {
                'message': 'Некорректные данные',
                'errors': serializer.errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    user = serializer.save()
    return Response(
        UserDataSerializer(user).data,
        status=status.HTTP_201_CREATED,
    )


# --------------------------------------------------
# Управление пользователями — аналог UsersController
# --------------------------------------------------

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def users_list(request):
    """Получение списка пользователей или создание нового пользователя."""

    # Список и создание пользователей доступны только администратору.
    if request.user.role != 'admin':
        return Response(
            {'message': 'Недостаточно прав для выполнения операции'},
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.method == 'GET':
        users = User.objects.all().order_by('id')

        # Пароль передаём только в виде маски, никогда не возвращаем хеш.
        serializer = UserDataSerializer(users, many=True)
        return Response(serializer.data)

    # Создание пользователя администратором.
    serializer = UserCreateSerializer(data=request.data)

    if not serializer.is_valid():
        email_errors = serializer.errors.get('email', [])

        if any(
            'уже существует' in str(error).lower()
            for error in email_errors
        ):
            return Response(
                {'message': 'Пользователь с таким email уже существует'},
                status=status.HTTP_409_CONFLICT,
            )

        return Response(
            {
                'message': 'Некорректные данные',
                'errors': serializer.errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    user = serializer.save()

    # Формат ответа соответствует старому UserInfo.
    return Response(
        {
            'id': user.pk,
            'email': user.email,
            'role': user.role,
            'usersName': user.users_name,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def user_detail(request, user_id):
    """Просмотр, редактирование и удаление пользователя."""

    user = User.objects.filter(pk=user_id).first()

    if user is None:
        return Response(
            {'message': 'Пользователь не найден'},
            status=status.HTTP_404_NOT_FOUND,
        )

    is_admin = request.user.role == 'admin'

    # GET: пользователь видит себя, администратор — всех.
    if request.method == 'GET':
        if request.user.pk != user.pk and not is_admin:
            return Response(
                {'message': 'Недостаточно прав для выполнения операции'},
                status=status.HTTP_403_FORBIDDEN,
            )

        return Response({
            'id': user.pk,
            'email': user.email,
            'role': user.role,
            'usersName': user.users_name,
        })

    # PUT: изменяем данные пользователя.
    if request.method == 'PUT':
        if request.user.pk != user.pk and not is_admin:
            return Response(
                {'message': 'Недостаточно прав для выполнения операции'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = UserUpdateSerializer(
            instance=user,
            data=request.data,
        )

        if not serializer.is_valid():
            email_errors = serializer.errors.get('email', [])

            if any(
                'уже существует' in str(error).lower()
                for error in email_errors
            ):
                return Response(
                    {'message': 'Пользователь с таким email уже существует'},
                    status=status.HTTP_409_CONFLICT,
                )

            return Response(
                {
                    'message': 'Некорректные данные',
                    'errors': serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = serializer.validated_data

        user.email = data['email']
        user.users_name = data['usersName']

        # Только администратор может менять роль и статус.
        if is_admin:
            if 'role' in data:
                user.role = data['role']

            if 'isAppruved' in data:
                user.is_appruved = data['isAppruved']

        # Маска или пустая строка означают, что пароль не меняем.
        new_password = data.get('password', '')

        if new_password and new_password != PASSWORD_MASK:
            user.set_password(new_password)

        user.save()

        return Response({
            'message': 'Пользователь успешно обновлен',
        })

    # DELETE: удаление доступно только администратору.
    if request.method == 'DELETE':
        if not is_admin:
            return Response(
                {'message': 'Недостаточно прав для выполнения операции'},
                status=status.HTTP_403_FORBIDDEN,
            )

        user.delete()

        return Response({
            'message': 'Пользователь успешно удален',
        })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def impersonate(request, user_id):
    # Только администратор может входить от имени другого пользователя.
    if request.user.role != 'admin' or request.auth.get('impersonator_id') is not None:
        return Response(
            {'message': 'Недостаточно прав для выполнения операции'},
            status=status.HTTP_403_FORBIDDEN
        )

    # Находим пользователя, от имени которого нужно войти.
    user = User.objects.filter(pk=user_id).first()

    if user is None:
        return Response(
            {'message': 'Пользователь не найден'},
            status=status.HTTP_404_NOT_FOUND
        )

    # Запрещаем вход от имени заблокированного пользователя.
    if not user.is_active or not user.is_appruved:
        return Response(
            {'message': 'Пользователь не активирован'},
            status=status.HTTP_403_FORBIDDEN
        )

    # Создаём JWT от имени выбранного пользователя.
    token = AccessToken.for_user(user)
    # Токен имперсонации действует только 15 минут.
    token.set_exp(lifetime=timedelta(minutes=15))

    # Сохраняем данные выбранного пользователя для совместимости с Vue.
    token['id'] = user.pk
    token['email'] = user.email
    token['role'] = user.role
    token['name'] = user.users_name
    token['displayName'] = user.users_name

    # Запоминаем, какой администратор инициировал переключение.
    token['impersonator_id'] = request.user.pk
    
    # Записываем факт переключения в журнал.
    ImpersonationLog.objects.create(
        admin=request.user,
        target_user=user
    )

    return Response(str(token), status=status.HTTP_200_OK)


# GET, POST, PUT /api/Category
@api_view(['GET', 'POST', 'PUT'])
@permission_classes([IsAuthenticated])
def category_list(request):

    # Получение всех категорий
    if request.method == 'GET':
        categories = Category.objects.all().order_by('id')
        serializer = CategorySerializer(categories, many=True)
        return Response(serializer.data)

    # Создание новой категории
    if request.method == 'POST':
        serializer = CategorySerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        category = serializer.save()
        return Response(
            CategorySerializer(category).data,
            status=200
        )

    # Изменение существующей категории
    if request.method == 'PUT':
        category_id = request.data.get('id')

        category = Category.objects.filter(pk=category_id).first()

        if category is None:
            return Response(
                {'message': 'Категория не найдена'},
                status=404
            )

        serializer = CategorySerializer(
            category,
            data=request.data
        )

        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        serializer.save()
        return Response(status=200)


# GET, DELETE /api/Category/{id}
@api_view(['GET', 'DELETE'])
@permission_classes([IsAuthenticated])
def category_detail(request, category_id):

    category = Category.objects.filter(pk=category_id).first()

    # Получение категории по ID
    if request.method == 'GET':
        if category is None:
            return Response(None, status=200)

        return Response(CategorySerializer(category).data)

    # Удаление категории
    if request.method == 'DELETE':
        if category is not None:
            category.delete()

        return Response(status=200)
    
# GET, POST, PUT /api/Product
@api_view(['GET', 'POST', 'PUT'])
@permission_classes([IsAuthenticated])
def product_list(request):

    if request.method == 'GET':
        products = Product.objects.select_related('category').order_by('id')
        serializer = ProductSerializer(products, many=True)
        return Response(serializer.data)

    if request.method == 'POST':
        serializer = ProductSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        product = serializer.save()
        return Response(
            ProductSerializer(product).data,
            status=200
        )

    if request.method == 'PUT':
        product_id = request.data.get('id')
        product = Product.objects.filter(pk=product_id).first()

        if product is None:
            return Response(
                {'message': 'Товар не найден'},
                status=404
            )

        serializer = ProductSerializer(product, data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        serializer.save()
        return Response(status=200)


# GET, DELETE /api/Product/{id}
@api_view(['GET', 'DELETE'])
@permission_classes([IsAuthenticated])
def product_detail(request, product_id):

    product = (
        Product.objects
        .select_related('category')
        .filter(pk=product_id)
        .first()
    )

    if request.method == 'GET':
        if product is None:
            return Response(None, status=200)

        return Response(ProductSerializer(product).data)

    if request.method == 'DELETE':
        if product is not None:
            product.delete()

        # Удаляем папку с фотографиями товара
        image_dir = (
            Path(settings.BASE_DIR)
            / 'wwwroot'
            / 'images'
            / 'product'
            / str(product_id)
        )

        if image_dir.exists():
            import shutil
            shutil.rmtree(image_dir)

            return Response(status=200)
    

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def product_delete_image(request):

    product_id = str(request.data.get('ProductId', ''))

    if not product_id or not product_id.isdigit():
        return Response(
            {'message': 'Не указан ProductId'},
            status=400
        )

    image_dir = (
        Path(settings.BASE_DIR)
        / 'wwwroot'
        / 'images'
        / 'product'
        / product_id
    )

    if not image_dir.exists():
        image_dir.mkdir(parents=True, exist_ok=True)
        return Response("Success on Create Directory")

    for file_path in image_dir.iterdir():
        if file_path.is_file():
            file_path.unlink()

    return Response("Success on DeleteImage")


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def product_load_image(request):
    product_id = request.data.get('strId')
    foto = request.FILES.get('foto')

    if not str(product_id).isdigit():
        return Response(
            {'error': 'Некорректный strId'},
            status=400
        )

    product = Product.objects.filter(pk=product_id).first()

    if product is None:
        return Response(
            {'error': 'Товар не найден'},
            status=404
        )

    image_dir = (
        Path(settings.BASE_DIR)
        / 'wwwroot'
        / 'images'
        / 'product'
        / str(product_id)
    )

    image_dir.mkdir(parents=True, exist_ok=True)

    # Удаляем предыдущие изображения
    for file_path in image_dir.iterdir():
        if file_path.is_file():
            file_path.unlink()

    file_name = 'X'

    if foto is not None:
        extension = Path(foto.name).suffix.lower()

        if extension not in ('.jpg', '.jpeg', '.png', '.webp', '.gif'):
            return Response(
                {'error': 'Недопустимый формат изображения'},
                status=400
            )

        file_name = f'{uuid4().hex}{extension}'
        file_path = image_dir / file_name

        with open(file_path, 'wb') as destination:
            for chunk in foto.chunks():
                destination.write(chunk)

        product.foto = file_name
        product.save(update_fields=['foto'])

    return Response({
        'success': True,
        'fileName': file_name,
        'timestamp': int(timezone.now().timestamp() * 1000)
    })


def get_new_order_number():
    today = timezone.localdate()

    # Количество заказов за текущую дату
    order_count = OrderHead.objects.filter(
    order_data=today
    ).count()

    # Формат: день.месяц.год/номер
    return f"{today.day}.{today.month}.{today.year}/{order_count + 1}"


@api_view(['GET', 'DELETE'])
@permission_classes([IsAuthenticated])
def order_head_detail(request, order_id):

    # Создание нового заказа: возвращаем заготовку
    if request.method == 'GET' and order_id == 0:
        user = request.user

        return Response({
            'id': 0,
            'userId': user.id,
            'usersName': user.users_name,
            'orderNumber': get_new_order_number(),
            'orderData': timezone.localdate().isoformat(),
            'totalPrice': 0
        })

    # Получаем существующий заказ
    order = OrderHead.objects.select_related('user').filter(
        pk=order_id
    ).first()

    # Удаление заказа
    if request.method == 'DELETE':
        if order is None:
            return Response(status=200)

        if request.user.role != 'admin' and order.user_id != request.user.id:
            return Response(
                {'message': 'Доступ запрещён'},
                status=403
            )

        order.delete()
        return Response(status=200)

    # Получение существующего заказа
    if order is None:
        return Response(None, status=200)

    if request.user.role != 'admin' and order.user_id != request.user.id:
        return Response(
            {'message': 'Доступ запрещён'},
            status=403
        )

    return Response({
        'id': order.id,
        'userId': order.user_id,
        'usersName': order.user.users_name,
        'orderNumber': order.order_number,
        'orderData': order.order_data.isoformat(),
        'totalPrice': 0
    }) 

def parse_order_date(value):
    if isinstance(value, date) and not isinstance(value, datetime):
        return value

    value = str(value)

    if 'T' not in value:
        return date.fromisoformat(value[:10])

    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))

    if timezone.is_aware(dt):
        dt = timezone.localtime(dt)

    return dt.date()


@api_view(['GET', 'POST', 'PUT'])
@permission_classes([IsAuthenticated])
def order_head_list(request):

    # ==========================================
    # POST — создание нового заказа
    # ==========================================
    if request.method == 'POST':
        data = request.data

        try:
            order_date = parse_order_date(data.get('orderData'))
        except ValueError:
            return Response(
                {'message': 'Некорректная дата заказа'},
                status=400
            )

        order = OrderHead.objects.create(
            user=request.user,
            order_number=get_new_order_number(),
            order_data=order_date
        )

        return Response({
            'id': order.id,
            'userId': order.user_id,
            'usersName': request.user.users_name,
            'orderNumber': order.order_number,
            'orderData': order.order_data.isoformat(),
            'totalPrice': 0
        }, status=200)

    # ==========================================
    # PUT — изменение существующего заказа
    # ==========================================
    if request.method == 'PUT':
        data = request.data

        order = OrderHead.objects.filter(
            pk=data.get('id')
        ).first()

        if order is None:
            return Response(
                {'message': 'Заказ не найден'},
                status=404
            )

        # Обычный пользователь может редактировать
        # только собственные заказы
        if request.user.role != 'admin' and order.user_id != request.user.id:
            return Response(
                {'message': 'Доступ запрещён'},
                status=403
            )

        try:
            order_date = parse_order_date(data.get('orderData'))
        except ValueError:
            return Response(
                {'message': 'Некорректная дата заказа'},
                status=400
            )

        order.order_number = data.get(
            'orderNumber',
            order.order_number
        )
        order.order_data = order_date

        # Администратор может изменить владельца заказа
        if request.user.role == 'admin':
            user_id = data.get('userId', order.user_id)

            if not User.objects.filter(pk=user_id).exists():
                return Response(
                    {'message': 'Пользователь не найден'},
                    status=400
                )

            order.user_id = user_id

        order.save()

        return Response(status=200)

    # ==========================================
    # GET — список заказов из OrderHeadView
    # ==========================================
    if request.user.role == 'admin':
        orders = OrderHeadView.objects.all()
    else:
        orders = OrderHeadView.objects.filter(
            user_id=request.user.id
        )

    result = []

    for order in orders.order_by('id'):
        result.append({
            'id': order.id,
            'userId': order.user_id,
            'usersName': order.users_name,
            'orderNumber': order.order_number,
            'orderData': order.order_data.isoformat(),
            'totalPrice': float(order.total_price)
        })

    return Response(result)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def order_detail_list(request, order_id):
    # Проверяем существование заказа и права доступа
    order = OrderHead.objects.filter(pk=order_id).first()

    if order is None:
        return Response([], status=200)

    if request.user.role != 'admin' and order.user_id != request.user.id:
        return Response(
            {'message': 'Доступ запрещён'},
            status=403
        )

    details = OrderDetail.objects.filter(
        order_id=order_id
    ).select_related('product').order_by('id')

    result = []

    for detail in details:
        price = detail.product.price

        result.append({
            'id': detail.id,
            'orderId': detail.order_id,
            'productId': detail.product_id,
            'qty': float(detail.qty),
            'productName': detail.product.product_name,
            'price': float(price),
            'rowSum': float(detail.qty * price)
        })

    return Response(result)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def order_detail_create(request):
    data = request.data

    order = OrderHead.objects.filter(
        pk=data.get('orderId')
    ).first()

    if order is None:
        return Response(
            {'message': 'Заказ не найден'},
            status=404
        )

    if request.user.role != 'admin' and order.user_id != request.user.id:
        return Response(
            {'message': 'Доступ запрещён'},
            status=403
        )

    product = Product.objects.filter(
        pk=data.get('productId')
    ).first()

    if product is None:
        return Response(
            {'message': 'Товар не найден'},
            status=404
        )

    from decimal import Decimal, InvalidOperation

    try:
        qty = Decimal(str(data.get('qty')))
        if not qty.is_finite() or qty <= 0:
            raise ValueError()
        if qty.as_tuple().exponent < -3 or qty >= Decimal('1000000000'):
            raise ValueError()
    except (InvalidOperation, ValueError, TypeError):
        return Response(
            {'message': 'Некорректное количество товара'},
            status=400
        )

    detail = OrderDetail.objects.create(
        order=order,
        product=product,
        qty=qty
    )

    return Response({
        'id': detail.id,
        'orderId': detail.order_id,
        'productId': detail.product_id,
        'qty': float(detail.qty),
        'productName': product.product_name,
        'price': float(product.price),
        'rowSum': float(detail.qty * product.price)
    }, status=200)
    
    
@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def order_detail_update(request):
    data = request.data

    detail = OrderDetail.objects.select_related('order').filter(
        pk=data.get('id')
    ).first()

    if detail is None:
        return Response(
            {'message': 'Позиция заказа не найдена'},
            status=404
        )

    if request.user.role != 'admin' and detail.order.user_id != request.user.id:
        return Response(
            {'message': 'Доступ запрещён'},
            status=403
        )

    product = Product.objects.filter(
        pk=data.get('productId')
    ).first()

    if product is None:
        return Response(
            {'message': 'Товар не найден'},
            status=404
        )

    from decimal import Decimal, InvalidOperation

    try:
        qty = Decimal(str(data.get('qty')))
        if not qty.is_finite() or qty <= 0:
            raise ValueError()
        if qty.as_tuple().exponent < -3 or qty >= Decimal('1000000000'):
            raise ValueError()
    except (InvalidOperation, ValueError, TypeError):
        return Response(
            {'message': 'Некорректное количество'},
            status=400
        )

    detail.product = product
    detail.qty = qty
    detail.save(update_fields=['product', 'qty'])

    return Response(status=200)


@api_view(['GET', 'POST', 'PUT'])
@permission_classes([IsAuthenticated])
def order_detail_save(request):
    if request.method == 'GET':
        return order_detail_get_one.cls().as_view()(
            request._request
        )

    if request.method == 'POST':
        return order_detail_create.cls().as_view()(
            request._request
        )

    return order_detail_update.cls().as_view()(
        request._request
    )

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def order_detail_delete(request, order_id):
    detail = OrderDetail.objects.select_related('order').filter(
        pk=order_id
    ).first()

    if detail is None:
        return Response(status=200)

    if request.user.role != 'admin' and detail.order.user_id != request.user.id:
        return Response(
            {'message': 'Доступ запрещён'},
            status=403
        )

    detail.delete()
    return Response(status=200)


@api_view(['GET', 'DELETE'])
@permission_classes([IsAuthenticated])
def order_detail_by_id(request, order_id):
    if request.method == 'GET':
        return order_detail_list.cls().as_view()(
            request._request, order_id=order_id
        )

    return order_detail_delete.cls().as_view()(
        request._request, order_id=order_id
    )
    
    
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def order_detail_get_one(request):
    detail_id = request.query_params.get('id')

    try:
        detail_id = int(detail_id)
    except (TypeError, ValueError):
        return Response(
            {'message': 'Некорректный ID позиции'},
            status=400
        )

    detail = OrderDetail.objects.select_related(
        'order', 'product'
    ).filter(pk=detail_id).first()

    if detail is None:
        return Response(
            {'message': 'Позиция заказа не найдена'},
            status=404
        )

    if request.user.role != 'admin' and detail.order.user_id != request.user.id:
        return Response(
            {'message': 'Доступ запрещён'},
            status=403
        )

    price = detail.product.price

    return Response({
        'id': detail.id,
        'orderId': detail.order_id,
        'productId': detail.product_id,
        'qty': float(detail.qty),
        'productName': detail.product.product_name,
        'price': float(price),
        'rowSum': float(detail.qty * price)
    })
    
    
from decimal import Decimal

def get_order_total(order):
    total = Decimal('0')

    details = OrderDetail.objects.filter(
        order=order
    ).select_related('product')

    for detail in details:
        total += detail.qty * detail.product.price

    return float(total)