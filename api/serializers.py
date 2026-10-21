
from rest_framework import serializers
from .models import User, Category, Product


class RegisterSerializer(serializers.Serializer):
    """Проверка данных для регистрации пользователя."""

    email = serializers.EmailField()
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        trim_whitespace=False,
    )
    usersName = serializers.CharField(
        max_length=250,
        required=False,
        allow_blank=True,
        default="",
    )

    def validate_email(self, value):
        # Не допускаем повторную регистрацию с тем же email.
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                "Пользователь с таким email уже существует"
            )
        return value


class LoginSerializer(serializers.Serializer):
    """Проверка данных для входа пользователя."""

    email = serializers.EmailField()
    password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
    )


# Маска для поля пароля в старом Vue-интерфейсе.
# Это не настоящий пароль и не хеш.
PASSWORD_MASK = "********"


class UserDataSerializer(serializers.ModelSerializer):
    """Формат пользователя, ожидаемый существующим Vue-клиентом."""

    password = serializers.SerializerMethodField()
    usersName = serializers.CharField(
        source='users_name',
        read_only=True,
    )
    isAppruved = serializers.BooleanField(
        source='is_appruved',
        read_only=True,
    )

    def get_password(self, obj) -> str:
        # Никогда не передаём клиенту пароль или его хеш.
        return PASSWORD_MASK

    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'password',
            'role',
            'usersName',
            'isAppruved',
        ]


class UserCreateSerializer(serializers.Serializer):
    """Проверка данных при создании пользователя администратором."""

    email = serializers.EmailField(max_length=250)
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        max_length=250,
        trim_whitespace=False,
    )
    usersName = serializers.CharField(max_length=250)
    role = serializers.CharField(
        max_length=250,
        required=False,
        default='user',
    )
    isAppruved = serializers.BooleanField(default=True)

    def validate_email(self, value):
        # Проверяем уникальность email без учёта регистра.
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                'Пользователь с таким email уже существует'
            )
        return value

    def create(self, validated_data):
        # Создаём пользователя через менеджер Django,
        # который хеширует пароль перед сохранением.
        return User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            users_name=validated_data['usersName'],
            role=validated_data.get('role', 'user'),
            is_appruved=validated_data.get('isAppruved', True),
        )


class UserUpdateSerializer(serializers.Serializer):
    """Проверка данных при редактировании пользователя."""

    email = serializers.EmailField(max_length=250)
    usersName = serializers.CharField(max_length=250)

    # Vue передаёт это поле даже тогда, когда пароль не меняли.
    password = serializers.CharField(
        required=False,
        allow_blank=True,
        trim_whitespace=False,
    )

    role = serializers.CharField(
        max_length=250,
        required=False,
    )
    isAppruved = serializers.BooleanField(required=False)

    def validate_email(self, value):
        # Разрешаем оставить собственный email без изменений,
        # но не разрешаем использовать email другого пользователя.
        queryset = User.objects.filter(email__iexact=value)

        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise serializers.ValidationError(
                'Пользователь с таким email уже существует'
            )

        return value

    def validate_password(self, value):
        # Маска означает, что администратор оставил пароль прежним.
        if value in ('', PASSWORD_MASK):
            return value

        if len(value) < 8:
            raise serializers.ValidationError(
                'Новый пароль должен содержать не менее 8 символов'
            )

        return value
    

class CategorySerializer(serializers.ModelSerializer):
    # Сохраняем название поля из ASP.NET Core API
    categoryName = serializers.CharField(
        source='category_name',
        max_length=250
    )

    class Meta:
        model = Category
        fields = ['id', 'categoryName']
        read_only_fields = ['id']
        

class ProductSerializer(serializers.ModelSerializer):
    productName = serializers.CharField(
        source='product_name',
        max_length=250
    )

    price = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        coerce_to_string=False
    )

    categoryId = serializers.PrimaryKeyRelatedField(
        source='category',
        queryset=Category.objects.all()
    )

    categoryName = serializers.CharField(
        source='category.category_name',
        read_only=True
    )

    foto = serializers.CharField(
        required=False,
        default='X'
    )

    class Meta:
        model = Product
        fields = [
            'id',
            'productName',
            'price',
            'categoryId',
            'categoryName',
            'foto'
        ]
        read_only_fields = ['id']
