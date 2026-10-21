"""OpenAPI annotations only; these serializers do not validate live requests."""

from decimal import Decimal

from drf_spectacular.extensions import OpenApiAuthenticationExtension
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, inline_serializer, OpenApiParameter, OpenApiResponse
from rest_framework import serializers as s

from .serializers import (
    RegisterSerializer, LoginSerializer, UserDataSerializer,
    UserCreateSerializer, UserUpdateSerializer, CategorySerializer, ProductSerializer,
)


class CookieJWTScheme(OpenApiAuthenticationExtension):
    target_class = 'api.authentication.CookieJWTAuthentication'
    name = ['jwtAuth', 'cookieAuth']

    def get_security_definition(self, auto_schema):
        return [
            {'type': 'http', 'scheme': 'bearer', 'bearerFormat': 'JWT'},
            {'type': 'apiKey', 'in': 'cookie', 'name': 'auth_token',
             'description': 'HttpOnly cookie set by Auth/login or Auth/register.'},
        ]

    def get_security_requirement(self, auto_schema):
        return [{'jwtAuth': []}, {'cookieAuth': []}]


def shape(name, **fields):
    return inline_serializer(name=name, fields=fields)


Message = shape('Message', message=s.CharField())
AuthError = shape('AuthenticationError', detail=s.CharField(), code=s.CharField(required=False))
UserInfo = shape('UserInfo', id=s.IntegerField(), email=s.EmailField(), role=s.CharField(), usersName=s.CharField())
Status = shape('Status', status=s.CharField(), message=s.CharField())


class CategoryUpdate(CategorySerializer):
    id = s.IntegerField()


class ProductUpdate(ProductSerializer):
    id = s.IntegerField()


Order = shape('Order', id=s.IntegerField(), userId=s.IntegerField(), usersName=s.CharField(),
              orderNumber=s.CharField(), orderData=s.DateField(), totalPrice=s.FloatField())
OrderCreate = shape('OrderCreate', orderData=s.CharField(help_text='ISO date or datetime.'))
OrderUpdate = shape('OrderUpdate', id=s.IntegerField(), orderData=s.CharField(help_text='ISO date or datetime.'),
                    orderNumber=s.CharField(required=False), userId=s.IntegerField(required=False, help_text='Admin only.'))
Detail = shape('OrderDetail', id=s.IntegerField(), orderId=s.IntegerField(), productId=s.IntegerField(),
               qty=s.FloatField(), productName=s.CharField(), price=s.FloatField(), rowSum=s.FloatField())


class DetailCreate(s.Serializer):
    orderId = s.IntegerField()
    productId = s.IntegerField()
    qty = s.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal('0.001'), coerce_to_string=False)


class DetailUpdate(s.Serializer):
    id = s.IntegerField()
    productId = s.IntegerField()
    qty = s.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal('0.001'), coerce_to_string=False)


ImageDelete = shape('ImageDelete', ProductId=s.CharField(help_text='Numeric product ID.'))
ImageUpload = shape('ImageUpload', strId=s.CharField(), foto=s.FileField(required=False))
ImageResult = shape('ImageResult', success=s.BooleanField(), fileName=s.CharField(), timestamp=s.IntegerField())


def operation(tag, response=None, request=None, errors=(), description='', parameters=(), code=200):
    responses = {code: response, 401: AuthError}
    responses.update({error: (
        OpenApiResponse(OpenApiTypes.OBJECT, description=(
            'Validation error: field names mapped to error lists, '
            'or an object containing message/errors or error.'
        )) if error == 400 else Message
    ) for error in errors})
    return dict(tags=[tag], request=request, responses=responses,
                description=description, parameters=list(parameters))


SCHEMAS = {
    'api_status': {'GET': operation('Status', Status)},
    'register': {'POST': operation('Auth', OpenApiTypes.STR, RegisterSerializer, (400,),
                                 'Returns a JSON JWT string and sets auth_token cookie.')},
    'login': {'POST': operation('Auth', OpenApiTypes.STR, LoginSerializer, (400,),
                              'Returns a JSON JWT string and sets auth_token cookie.')},
    'me': {'GET': operation('Auth', UserInfo)},
    'logout': {'POST': operation('Auth', Message, description='Clears auth_token cookie; issued JWTs remain valid until expiry.')},
    'users_list': {
        'GET': operation('Users', UserDataSerializer(many=True), errors=(403,), description='Admin only.'),
        'POST': operation('Users', UserInfo, UserCreateSerializer, (400, 403, 409), 'Admin only.', code=201),
    },
    'user_detail': {
        'GET': operation('Users', UserInfo, errors=(403, 404), description='Own profile or admin.'),
        'PUT': operation('Users', Message, UserUpdateSerializer, (400, 403, 404, 409),
                         'Own profile or admin. Only admins can change role and isAppruved. Empty or masked password leaves it unchanged.'),
        'DELETE': operation('Users', Message, errors=(403, 404), description='Admin only.'),
    },
    'category_list': {
        'GET': operation('Categories', CategorySerializer(many=True)),
        'POST': operation('Categories', CategorySerializer, CategorySerializer, (400,)),
        'PUT': operation('Categories', None, CategoryUpdate, (400, 404)),
    },
    'category_detail': {
        'GET': operation('Categories', CategorySerializer, description='Empty response with status 200 if category does not exist.'),
        'DELETE': operation('Categories'),
    },
    'product_list': {
        'GET': operation('Products', ProductSerializer(many=True)),
        'POST': operation('Products', ProductSerializer, ProductSerializer, (400,)),
        'PUT': operation('Products', None, ProductUpdate, (400, 404)),
    },
    'product_detail': {
        'GET': operation('Products', ProductSerializer, description='Empty response with status 200 if product does not exist.'),
        'DELETE': operation('Products', description='Deletes product and its image directory. Existing handler returns 200 only when the directory exists; otherwise it raises a server error.'),
    },
    'product_delete_image': {'POST': operation('Products', OpenApiTypes.STR, ImageDelete, (400,))},
    'product_load_image': {'POST': operation('Products', ImageResult, {'multipart/form-data': ImageUpload}, (400, 404))},
    'order_head_list': {
        'GET': operation('OrderHead', Order.__class__(many=True), description='Admins see all orders; users see their own orders.'),
        'POST': operation('OrderHead', Order, OrderCreate, (400,), 'Owner and order number are assigned by the server.'),
        'PUT': operation('OrderHead', None, OrderUpdate, (400, 403, 404)),
    },
    'order_head_detail': {
        'GET': operation('OrderHead', Order, errors=(403,), description='ID 0 returns a new order template. Missing orders return an empty 200 response. Own orders or admin.'),
        'DELETE': operation('OrderHead', errors=(403,), description='Own orders or admin. Missing orders return 200.'),
    },
    'order_detail_save': {
        'GET': operation('OrderDetail', Detail, errors=(400, 403, 404),
                         parameters=[OpenApiParameter('id', int, required=True, description='Order detail ID.')]),
        'POST': operation('OrderDetail', Detail, DetailCreate, (400, 403, 404)),
        'PUT': operation('OrderDetail', None, DetailUpdate, (400, 403, 404)),
    },
    'order_detail_by_id': {
        'GET': operation('OrderDetail', Detail.__class__(many=True), errors=(403,),
                         description='order_id is the ORDER ID. Returns its positions; missing orders return []. Own orders or admin.'),
        'DELETE': operation('OrderDetail', errors=(403,),
                            description='order_id is the POSITION ID. Missing positions return 200. Own orders or admin.'),
    },
}

# Login returns a shop message for rejected credentials, not DRF's detail field.
SCHEMAS['login']['POST']['responses'][401] = Message
SCHEMAS['product_detail']['DELETE']['responses'][500] = OpenApiResponse(
    description='Existing handler raises a server error if the image directory does not exist.'
)


def documented(name):
    """Apply method-specific extend_schema annotations above @api_view."""
    def decorate(view):
        for method, options in SCHEMAS[name].items():
            view = extend_schema(methods=[method], operation_id=f'{name}_{method.lower()}', **options)(view)
        return view
    return decorate
