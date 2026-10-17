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
		self.assertEqual(own_response.data['password'], PASSWORD_MASK)
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
		self.assertEqual(response.data['password'], PASSWORD_MASK)
		created_user = User.objects.get(email='new@example.com')
		self.assertTrue(created_user.check_password('NewPassword123!'))
