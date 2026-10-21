from django.test import TestCase
from rest_framework.test import APIClient

from .models import User
from .serializers import PASSWORD_MASK


class UserAdminApiTests(TestCase):
	def setUp(self):
		self.admin = User.objects.create_user(
			email='admin@example.com',
			password='AdminPassword123!',
			role='admin',
		)
		self.user = User.objects.create_user(
			email='user@example.com',
			password='UserPassword123!',
		)

	def test_admin_can_list_users_without_exposing_password_hashes(self):
		client = APIClient()
		client.force_authenticate(user=self.admin)

		response = client.get('/api/Users')

		self.assertEqual(response.status_code, 200)
		self.assertEqual(len(response.data), 2)
		self.assertEqual(response.data[0]['password'], PASSWORD_MASK)
		self.assertEqual(
			set(response.data[0]),
			{'id', 'email', 'password', 'role', 'usersName', 'isAppruved'},
		)

	def test_user_list_and_creation_are_for_admins_only(self):
		client = APIClient()
		client.force_authenticate(user=self.user)

		list_response = client.get('/api/Users')
		create_response = client.post('/api/Users', {}, format='json')

		self.assertEqual(list_response.status_code, 403)
		self.assertEqual(create_response.status_code, 403)

	def test_user_can_read_self_but_not_another_user(self):
		client = APIClient()
		client.force_authenticate(user=self.user)

		own_response = client.get(f'/api/Users/{self.user.pk}')
		other_response = client.get(f'/api/Users/{self.admin.pk}')

		self.assertEqual(own_response.status_code, 200)
		self.assertEqual(own_response.data, {
			'id': self.user.pk,
			'email': self.user.email,
			'role': self.user.role,
			'usersName': self.user.users_name,
		})
		self.assertEqual(other_response.status_code, 403)

	def test_admin_can_create_user_with_hashed_password(self):
		client = APIClient()
		client.force_authenticate(user=self.admin)

		response = client.post(
			'/api/Users',
			{
				'email': 'new@example.com',
				'password': 'NewPassword123!',
				'usersName': 'New User',
				'role': 'user',
				'isAppruved': True,
			},
			format='json',
		)

		self.assertEqual(response.status_code, 201)
		created_user = User.objects.get(email='new@example.com')
		self.assertEqual(response.data, {
			'id': created_user.pk,
			'email': 'new@example.com',
			'role': 'user',
			'usersName': 'New User',
		})
		self.assertNotEqual(created_user.password, 'NewPassword123!')
		self.assertTrue(created_user.check_password('NewPassword123!'))
		self.assertFalse(created_user.check_password('WrongPassword123!'))


class JWTAuthenticationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.users = [
            User.objects.create_user(
                email=f'{role}@jwt.example.com',
                password='OrdinaryPassword123!',
                role=role,
            )
            for role in ('admin', 'user')
        ]

    def test_login_and_header_authentication_for_both_roles(self):
        for user in self.users:
            with self.subTest(role=user.role):
                client = APIClient()
                response = client.post('/api/Auth/login', {
                    'email': user.email,
                    'password': 'OrdinaryPassword123!',
                }, format='json')
                self.assertEqual(response.status_code, 200)
                token = response.data
                self.assertEqual(response.cookies['auth_token'].value, token)
                client.cookies.clear()
                client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
                response = client.get('/api/Auth/me')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data['id'], user.pk)
                self.assertEqual(response.data['role'], user.role)

    def test_cookie_authentication_and_logout_for_both_roles(self):
        from rest_framework_simplejwt.tokens import AccessToken
        for user in self.users:
            with self.subTest(role=user.role):
                client = APIClient()
                client.cookies['auth_token'] = str(AccessToken.for_user(user))
                response = client.get('/api/Auth/me')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data['id'], user.pk)
                response = client.post('/api/Auth/logout')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.cookies['auth_token']['max-age'], 0)
                self.assertEqual(client.get('/api/Auth/me').status_code, 401)

    def test_tokens_with_impersonator_claim_are_rejected(self):
        from rest_framework_simplejwt.tokens import AccessToken
        for user in self.users:
            for value in (self.users[0].pk, None, 0, ''):
                for source in ('header', 'cookie'):
                    with self.subTest(role=user.role, value=value, source=source):
                        token = AccessToken.for_user(user)
                        token['impersonator_id'] = value
                        client = APIClient()
                        if source == 'header':
                            client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
                        else:
                            client.cookies['auth_token'] = str(token)
                        response = client.get('/api/Auth/me')
                        self.assertEqual(response.status_code, 401)
                        self.assertEqual(response.data['code'], 'token_not_valid')

    def test_removed_endpoint_does_not_resolve(self):
        from django.urls import Resolver404, resolve
        with self.assertRaises(Resolver404):
            resolve(f'/api/Auth/impersonate/{self.users[1].pk}')

    def test_invalid_tokens_are_rejected(self):
        from datetime import timedelta
        from rest_framework_simplejwt.tokens import AccessToken
        expired = AccessToken.for_user(self.users[0])
        expired.set_exp(lifetime=timedelta(seconds=-1))
        for token in ('invalid-token', str(expired)):
            for source in ('header', 'cookie'):
                with self.subTest(source=source, token=token):
                    client = APIClient()
                    if source == 'header':
                        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
                    else:
                        client.cookies['auth_token'] = token
                    self.assertEqual(client.get('/api/Auth/me').status_code, 401)
