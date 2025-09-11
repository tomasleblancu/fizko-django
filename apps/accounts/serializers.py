"""
Serializers for the accounts app - User management and authentication
"""
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError

from .models import User, UserProfile, Role, UserRole
from apps.core.validators import validate_phone_number


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for User model with password handling and validation
    """
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    phone = serializers.CharField(validators=[validate_phone_number], required=False, allow_blank=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 
            'phone', 'is_verified', 'is_active', 'date_joined',
            'password', 'password_confirm'
        ]
        read_only_fields = ['id', 'date_joined', 'is_verified']
        extra_kwargs = {
            'email': {'required': True},
            'first_name': {'required': True},
            'last_name': {'required': True},
        }
    
    def validate(self, attrs):
        """Custom validation for password confirmation"""
        if 'password' in attrs and 'password_confirm' in attrs:
            if attrs['password'] != attrs['password_confirm']:
                raise serializers.ValidationError({
                    'password_confirm': 'Las contraseñas no coinciden'
                })
        return attrs
    
    def create(self, validated_data):
        """Create user with encrypted password"""
        validated_data.pop('password_confirm', None)
        password = validated_data.pop('password')
        user = User.objects.create_user(**validated_data)
        user.set_password(password)
        user.save()
        return user
    
    def update(self, instance, validated_data):
        """Update user, handling password changes"""
        validated_data.pop('password_confirm', None)
        password = validated_data.pop('password', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        if password:
            instance.set_password(password)
        
        instance.save()
        return instance


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for UserProfile model
    """
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    phone = serializers.CharField(validators=[validate_phone_number], required=False, allow_blank=True)
    
    class Meta:
        model = UserProfile
        fields = [
            'id', 'user', 'user_email', 'user_name', 'position', 
            'phone', 'avatar', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'user_email', 'user_name']


class RoleSerializer(serializers.ModelSerializer):
    """
    Serializer for Role model with permission management
    """
    user_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Role
        fields = [
            'id', 'name', 'description', 'permissions', 
            'created_at', 'updated_at', 'user_count'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'user_count']
    
    def validate_permissions(self, value):
        """Validate permissions structure"""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Los permisos deben ser un objeto JSON válido")
        
        # Define valid permission categories and actions
        valid_categories = [
            'companies', 'documents', 'forms', 'expenses', 'tasks', 
            'analytics', 'settings', 'users'
        ]
        valid_actions = ['create', 'read', 'update', 'delete', 'export']
        
        for category, actions in value.items():
            if category not in valid_categories:
                raise serializers.ValidationError(f"Categoría de permisos inválida: {category}")
            
            if not isinstance(actions, (list, dict)):
                raise serializers.ValidationError(f"Las acciones para {category} deben ser una lista o objeto")
            
            if isinstance(actions, list):
                for action in actions:
                    if action not in valid_actions:
                        raise serializers.ValidationError(f"Acción inválida: {action}")
        
        return value


class UserRoleSerializer(serializers.ModelSerializer):
    """
    Serializer for UserRole model with nested user and company information
    """
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    role_name = serializers.CharField(source='role.name', read_only=True)
    company_name = serializers.CharField(source='company.name', read_only=True)
    company_full_rut = serializers.CharField(source='company.full_rut', read_only=True)
    
    class Meta:
        model = UserRole
        fields = [
            'id', 'user', 'user_email', 'user_name', 
            'company', 'company_name', 'company_full_rut',
            'role', 'role_name', 'active', 
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at', 
            'user_email', 'user_name', 'role_name', 
            'company_name', 'company_full_rut'
        ]
    
    def validate(self, attrs):
        """Validate unique constraint"""
        user = attrs.get('user')
        company = attrs.get('company')
        role = attrs.get('role')
        
        # Check for existing active role for this user-company combination
        if user and company and role:
            existing = UserRole.objects.filter(
                user=user, company=company, role=role, active=True
            ).exclude(id=self.instance.id if self.instance else None)
            
            if existing.exists():
                raise serializers.ValidationError(
                    "El usuario ya tiene este rol asignado para esta empresa"
                )
        
        return attrs


class UserDetailSerializer(UserSerializer):
    """
    Detailed user serializer with profile and roles information
    """
    profile = UserProfileSerializer(read_only=True)
    user_roles = UserRoleSerializer(many=True, read_only=True)
    total_companies = serializers.SerializerMethodField()
    active_roles = serializers.SerializerMethodField()
    
    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + [
            'profile', 'user_roles', 'total_companies', 'active_roles'
        ]
    
    def get_total_companies(self, obj):
        """Get total number of companies user has access to"""
        return obj.user_roles.filter(active=True).values('company').distinct().count()
    
    def get_active_roles(self, obj):
        """Get list of active role names"""
        return list(
            obj.user_roles.filter(active=True)
            .select_related('role')
            .values_list('role__name', flat=True)
            .distinct()
        )


class UserListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for user listings
    """
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    total_companies = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'full_name',
            'is_verified', 'is_active', 'date_joined', 'total_companies'
        ]
        read_only_fields = ['id', 'date_joined', 'full_name', 'total_companies']
    
    def get_total_companies(self, obj):
        """Get total number of companies user has access to"""
        return obj.user_roles.filter(active=True).values('company').distinct().count()


class PasswordResetSerializer(serializers.Serializer):
    """
    Serializer for password reset requests
    """
    email = serializers.EmailField()
    
    def validate_email(self, value):
        """Validate that email exists in the system"""
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError("No existe un usuario con este email")
        return value


class PasswordChangeSerializer(serializers.Serializer):
    """
    Serializer for password changes
    """
    current_password = serializers.CharField()
    new_password = serializers.CharField(validators=[validate_password])
    new_password_confirm = serializers.CharField()
    
    def validate_current_password(self, value):
        """Validate current password"""
        user = self.context.get('request').user
        if not user.check_password(value):
            raise serializers.ValidationError("Contraseña actual incorrecta")
        return value
    
    def validate(self, attrs):
        """Validate password confirmation"""
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({
                'new_password_confirm': 'Las contraseñas no coinciden'
            })
        return attrs


class UserVerificationSerializer(serializers.Serializer):
    """
    Serializer for user email verification
    """
    verification_token = serializers.CharField()
    
    def validate_verification_token(self, value):
        """Validate verification token format"""
        if not value or len(value) < 32:
            raise serializers.ValidationError("Token de verificación inválido")
        return value


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Custom JWT token serializer that includes user data
    """
    def validate(self, attrs):
        data = super().validate(attrs)
        
        # Add user data to response
        data.update({
            'user': {
                'id': self.user.id,
                'email': self.user.email,
                'first_name': self.user.first_name,
                'last_name': self.user.last_name,
                'is_verified': self.user.is_verified,
            }
        })
        
        return data


class UserRegistrationSerializer(serializers.ModelSerializer):
    """
    Serializer for user registration
    """
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    
    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'password', 'password_confirm']
        extra_kwargs = {
            'email': {'required': True},
            'first_name': {'required': True},
            'last_name': {'required': True},
        }
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({
                'password_confirm': 'Las contraseñas no coinciden'
            })
        return attrs
    
    def create(self, validated_data):
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        user = User.objects.create_user(**validated_data)
        user.set_password(password)
        user.save()
        return user


class ChangePasswordSerializer(serializers.Serializer):
    """
    Serializer for password change
    """
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password])
    new_password_confirm = serializers.CharField(required=True)
    
    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({
                'new_password_confirm': 'Las contraseñas no coinciden'
            })
        return attrs


class ProfileUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating user profile
    """
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'phone']