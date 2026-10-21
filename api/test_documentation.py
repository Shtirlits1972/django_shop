import json
from datetime import timedelta
from io import StringIO
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from .models import User


@override_settings(STORAGES={
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
})
class DocumentationTests(TestCase):
    urls = ('/api/schema/', '/api/docs/', '/api/redoc/')

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(email='docs-admin@example.com', role='admin')
        cls.user = User.objects.create_user(email='docs-user@example.com', role='user', is_staff=True)

    def client_for(self, user, source):
        client = APIClient()
        token = str(AccessToken.for_user(user))
        if source == 'header':
            client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        else:
            client.cookies['auth_token'] = token
        return client

    def test_anonymous_access_is_denied(self):
        for url in self.urls:
            with self.subTest(url=url):
                self.assertEqual(APIClient().get(url).status_code, 401)

    def test_non_admin_access_is_denied_for_header_and_cookie(self):
        for source in ('header', 'cookie'):
            client = self.client_for(self.user, source)
            for url in self.urls:
                with self.subTest(source=source, url=url):
                    self.assertEqual(client.get(url).status_code, 403)

    def test_admin_access_uses_shop_role_for_header_and_cookie(self):
        self.assertFalse(self.admin.is_staff)
        for source in ('header', 'cookie'):
            client = self.client_for(self.admin, source)
            for url in self.urls:
                with self.subTest(source=source, url=url):
                    self.assertEqual(client.get(url).status_code, 200)

    def test_invalid_and_expired_tokens_are_denied(self):
        expired = AccessToken.for_user(self.admin)
        expired.set_exp(lifetime=timedelta(seconds=-1))
        impersonation = AccessToken.for_user(self.admin)
        impersonation['impersonator_id'] = self.user.pk
        for token in ('invalid', str(expired), str(impersonation)):
            for source in ('header', 'cookie'):
                client = APIClient()
                if source == 'header':
                    client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
                else:
                    client.cookies['auth_token'] = token
                for url in self.urls:
                    with self.subTest(source=source, url=url):
                        self.assertEqual(client.get(url).status_code, 401)

    def test_header_takes_precedence_over_cookie(self):
        client = self.client_for(self.admin, 'cookie')
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        for url in self.urls:
            self.assertEqual(client.get(url).status_code, 403)

    def test_schema_covers_existing_api_contract(self):
        response = self.client_for(self.admin, 'header').get('/api/schema/', HTTP_ACCEPT='application/vnd.oai.openapi+json')
        self.assertEqual(response.status_code, 200)
        schema = json.loads(response.content)
        expected = {
            '/api/status/': {'get'},
            '/api/Auth/register': {'post'}, '/api/Auth/login': {'post'},
            '/api/Auth/me': {'get'}, '/api/Auth/logout': {'post'},
            '/api/Users': {'get', 'post'}, '/api/Users/{user_id}': {'get', 'put', 'delete'},
            '/api/Category': {'get', 'post', 'put'}, '/api/Category/{category_id}': {'get', 'delete'},
            '/api/Product': {'get', 'post', 'put'}, '/api/Product/{product_id}': {'get', 'delete'},
            '/api/Products/DeleteImage': {'post'}, '/api/Products/LoadImage': {'post'},
            '/api/OrderHead': {'get', 'post', 'put'}, '/api/OrderHead/{order_id}': {'get', 'delete'},
            '/api/OrderDetail': {'get', 'post', 'put'}, '/api/OrderDetail/{order_id}': {'get', 'delete'},
        }
        self.assertEqual(set(schema['paths']), set(expected))
        for path, methods in expected.items():
            self.assertEqual(set(schema['paths'][path]), methods)
        paths = schema['paths']
        self.assertEqual(paths['/api/Auth/login']['post']['responses']['200']['content']['application/json']['schema']['type'], 'string')
        self.assertIn('201', paths['/api/Users']['post']['responses'])
        self.assertIn('multipart/form-data', paths['/api/Products/LoadImage']['post']['requestBody']['content'])
        self.assertEqual(paths['/api/OrderDetail']['get']['parameters'][0]['name'], 'id')
        components = schema['components']['schemas']
        for name in ('CategoryUpdateRequest', 'ProductUpdateRequest', 'OrderUpdateRequest', 'DetailUpdateRequest'):
            self.assertIn('id', components[name]['required'])
        self.assertEqual(components['Order']['properties']['totalPrice']['type'], 'number')
        self.assertEqual(components['OrderDetail']['properties']['qty']['type'], 'number')
        schemes = schema['components']['securitySchemes']
        self.assertEqual(schemes['jwtAuth']['scheme'], 'bearer')
        self.assertEqual(schemes['cookieAuth']['name'], 'auth_token')
        self.assertIn({'jwtAuth': []}, paths['/api/Auth/me']['get']['security'])

    def test_collected_sidecar_assets_are_served_with_debug_false(self):
        import re

        with TemporaryDirectory() as root, override_settings(
            DEBUG=False, STATIC_ROOT=root, STATICFILES_DIRS=[],
            STORAGES={
                'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
                'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
            },
        ):
            call_command('collectstatic', interactive=False, verbosity=0, stdout=StringIO())
            client = self.client_for(self.admin, 'cookie')
            assets = []
            for url in ('/api/docs/', '/api/redoc/'):
                response = client.get(url)
                self.assertEqual(response.status_code, 200)
                html = response.content.decode()
                self.assertNotIn('cdn.jsdelivr.net', html)
                self.assertNotIn('unpkg.com', html)
                assets.extend(re.findall(r'(?:src|href)="(/static/drf_spectacular_sidecar/[^\"]+)"', html))
            self.assertGreaterEqual(len(assets), 4)
            for asset in assets:
                response = client.get(asset)
                self.assertEqual(response.status_code, 200, asset)
                response.close()
