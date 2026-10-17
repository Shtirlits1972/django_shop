#    email = "test@example.com"
#   password = "TestPassword123!"


from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin


class UserManager(BaseUserManager):
    """Создание обычных пользователей и администраторов."""

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Необходимо указать email")

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)

        # Django сохранит пароль в виде хеша, а не открытого текста.
        user.set_password(password)
        user.save(using=self._db)

        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if not extra_fields["is_staff"]:
            raise ValueError("Администратор должен иметь is_staff=True")

        if not extra_fields["is_superuser"]:
            raise ValueError("Администратор должен иметь is_superuser=True")

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Пользователь интернет-магазина."""

    email = models.EmailField(unique=True, max_length=250)
    users_name = models.CharField(max_length=250, blank=True, default="")
    role = models.CharField(max_length=250, default="user")
    is_appruved = models.BooleanField(default=True)

    # Поля, необходимые для системы авторизации Django.
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        db_table = "Users"

    def __str__(self):
        return self.email
    
    

class ImpersonationLog(models.Model):
    # Администратор, инициировавший переключение
    admin = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='impersonation_logs_as_admin'
    )

    # Пользователь, от имени которого выполнен вход
    target_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='impersonation_logs_as_target'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.admin} -> {self.target_user} ({self.created_at})'
    
    
class ImpersonationActionLog(models.Model):
    # Администратор, от имени которого выполняется действие
    admin = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='impersonation_actions_as_admin'
    )

    # Пользователь, под которым работает администратор
    target_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='impersonation_actions_as_target'
    )

    # Информация об HTTP-запросе
    method = models.CharField(max_length=10)
    path = models.CharField(max_length=500)
    # HTTP-код ответа сервера.
    status_code = models.PositiveSmallIntegerField(
        null=True,
        blank=True
    )

    # Время выполнения действия
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        
        
class Category(models.Model):
    # Наименование категории
    category_name = models.CharField(max_length=250)

    class Meta:
        db_table = 'Category'

    def __str__(self):
        return self.category_name


class Product(models.Model):
    product_name = models.CharField(max_length=250)
    price = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        db_column='CategoryId'
    )

    foto = models.CharField(max_length=255, default='X')

    class Meta:
        db_table = 'Product'

    def __str__(self):
        return self.product_name
    
    
class OrderHead(models.Model):
    user = models.ForeignKey(
        'api.User',
        on_delete=models.PROTECT,
        db_column='userId'
    )

    order_number = models.CharField(
        max_length=50,
        db_column='orderNumber'
    )

    order_data = models.DateField(
        db_column='orderData'
    )

    class Meta:
        db_table = 'OrderHead'

    def __str__(self):
        return self.order_number
    
    
class OrderDetail(models.Model):
    order = models.ForeignKey(
        OrderHead,
        on_delete=models.CASCADE,
        db_column='orderId',
        related_name='details'
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        db_column='ProductId'
    )

    qty = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        default=0,
        db_column='Qty'
    )

    class Meta:
        db_table = 'OrderDetail'

    def __str__(self):
        return f"Заказ {self.order_id}, товар {self.product_id}, количество {self.qty}"
    
    
class OrderHeadView(models.Model):
    order_number = models.CharField(
        max_length=50,
        db_column='orderNumber'
    )

    user_id = models.IntegerField(
        db_column='userId'
    )

    users_name = models.CharField(
        max_length=255,
        db_column='usersName'
    )

    order_data = models.DateField(
        db_column='orderData'
    )

    total_price = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        db_column='totalPrice'
    )

    class Meta:
        managed = False
        db_table = 'OrderHeadView'

    def __str__(self):
        return self.order_number
