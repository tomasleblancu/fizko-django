"""
Serializers for the accounts app - User management and authentication
"""
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError

from .models import User, UserProfile, Role, UserRole, VerificationCode, TeamInvitation
from apps.core.validators import validate_phone_number


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for User model with password handling and validation
    """
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    phone = serializers.CharField(validators=[validate_phone_number], required=True, allow_blank=False)
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'phone', 'is_verified', 'email_verified', 'phone_verified',
            'is_active', 'date_joined', 'password', 'password_confirm'
        ]
        read_only_fields = ['id', 'date_joined', 'is_verified', 'email_verified', 'phone_verified']
        extra_kwargs = {
            'email': {'required': True},
            'first_name': {'required': True},
            'last_name': {'required': True},
            'phone': {'required': True},
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
                'email_verified': self.user.email_verified,
                'phone_verified': self.user.phone_verified,
                'phone': getattr(self.user, 'phone', ''),
            }
        })
        
        return data


class UserRegistrationSerializer(serializers.ModelSerializer):
    """
    Serializer for user registration
    """
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    phone = serializers.CharField(validators=[validate_phone_number], required=True, allow_blank=False)
    invitation_token = serializers.UUIDField(required=False, write_only=True)

    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'phone', 'password', 'password_confirm', 'invitation_token']
        extra_kwargs = {
            'email': {'required': True},
            'first_name': {'required': True},
            'last_name': {'required': True},
            'phone': {'required': True},
        }

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({
                'password_confirm': 'Las contraseñas no coinciden'
            })

        # Validate invitation token if provided
        invitation_token = attrs.get('invitation_token')
        if invitation_token:
            try:
                invitation = TeamInvitation.objects.get(token=invitation_token, status='pending')
                if not invitation.can_be_accepted():
                    raise serializers.ValidationError({
                        'invitation_token': 'La invitación ha expirado o no es válida'
                    })

                # Check if email matches the invitation
                if attrs['email'].lower() != invitation.email.lower():
                    raise serializers.ValidationError({
                        'email': 'El email debe coincidir con el de la invitación'
                    })

                attrs['_invitation'] = invitation
            except TeamInvitation.DoesNotExist:
                raise serializers.ValidationError({
                    'invitation_token': 'Token de invitación inválido'
                })

        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        invitation_token = validated_data.pop('invitation_token', None)
        invitation = validated_data.pop('_invitation', None)

        password = validated_data.pop('password')
        user = User.objects.create_user(**validated_data)
        user.set_password(password)
        user.save()

        # If there's an invitation, store it for later processing
        if invitation:
            user._invitation = invitation

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


class VerificationCodeSerializer(serializers.ModelSerializer):
    """
    Serializer for verification codes
    """
    class Meta:
        model = VerificationCode
        fields = ['id', 'verification_type', 'expires_at', 'attempts', 'last_resent_at', 'created_at']
        read_only_fields = ['id', 'expires_at', 'attempts', 'last_resent_at', 'created_at']


class SendVerificationCodeSerializer(serializers.Serializer):
    """
    Serializer for sending verification codes
    """
    verification_type = serializers.ChoiceField(choices=VerificationCode.VERIFICATION_TYPES)

    def validate_verification_type(self, value):
        """Validate that the user needs this verification"""
        user = self.context.get('user')
        if not user:
            raise serializers.ValidationError("Usuario no encontrado")

        if value == 'email' and user.email_verified:
            raise serializers.ValidationError("El email ya está verificado")
        elif value == 'phone' and user.phone_verified:
            raise serializers.ValidationError("El teléfono ya está verificado")

        return value


class VerifyCodeSerializer(serializers.Serializer):
    """
    Serializer for verifying codes
    """
    verification_type = serializers.ChoiceField(choices=VerificationCode.VERIFICATION_TYPES)
    code = serializers.CharField(max_length=6, min_length=6)

    def validate(self, attrs):
        """Validate the verification code"""
        user = self.context.get('user')
        if not user:
            raise serializers.ValidationError("Usuario no encontrado")

        verification_type = attrs['verification_type']
        code = attrs['code']

        # Find valid verification code
        verification_code = VerificationCode.objects.filter(
            user=user,
            verification_type=verification_type,
            code=code,
            is_used=False
        ).first()

        if not verification_code:
            raise serializers.ValidationError({
                'code': 'Código de verificación inválido'
            })

        if verification_code.is_expired:
            raise serializers.ValidationError({
                'code': 'El código ha expirado. Solicita uno nuevo.'
            })

        # Increment attempts
        verification_code.attempts += 1
        verification_code.save(update_fields=['attempts'])

        # Too many attempts
        if verification_code.attempts > 5:
            verification_code.mark_as_used()
            raise serializers.ValidationError({
                'code': 'Demasiados intentos. Solicita un nuevo código.'
            })

        attrs['verification_code'] = verification_code
        return attrs


class ResendVerificationCodeSerializer(serializers.Serializer):
    """
    Serializer for resending verification codes
    """
    verification_type = serializers.ChoiceField(choices=VerificationCode.VERIFICATION_TYPES)

    def validate_verification_type(self, value):
        """Validate that code can be resent"""
        user = self.context.get('user')
        if not user:
            raise serializers.ValidationError("Usuario no encontrado")

        # Check if already verified
        if value == 'email' and user.email_verified:
            raise serializers.ValidationError("El email ya está verificado")
        elif value == 'phone' and user.phone_verified:
            raise serializers.ValidationError("El teléfono ya está verificado")

        # Check cooldown period
        latest_code = VerificationCode.objects.filter(
            user=user,
            verification_type=value
        ).order_by('-created_at').first()

        if latest_code and not latest_code.can_resend():
            raise serializers.ValidationError(
                "Debes esperar 5 minutos antes de solicitar un nuevo código"
            )

        return value


class InviteToTeamSerializer(serializers.Serializer):
    """
    Serializer for inviting users to teams
    Now supports multiple companies
    """
    email = serializers.EmailField(required=True)
    company_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=True,
        min_length=1,
        help_text="Lista de IDs de empresas a las que invitar"
    )
    role_id = serializers.IntegerField(required=True)

    def validate_email(self, value):
        """Validate email format"""
        return value.lower().strip()

    def validate(self, attrs):
        """Validate invitation data for multiple companies"""
        from apps.companies.models import Company

        user = self.context.get('user')
        if not user:
            raise serializers.ValidationError("Usuario no encontrado")

        email = attrs['email']
        company_ids = attrs['company_ids']
        role_id = attrs['role_id']

        # Validate all companies exist
        companies = []
        for company_id in company_ids:
            try:
                company = Company.objects.get(id=company_id)
                companies.append(company)
            except Company.DoesNotExist:
                raise serializers.ValidationError({
                    'company_ids': f'La empresa con ID {company_id} no existe'
                })

        # Check if user is owner of ALL specified companies
        for company in companies:
            user_role = UserRole.objects.filter(
                user=user,
                company=company,
                role__name='owner',
                active=True
            ).first()

            if not user_role:
                raise serializers.ValidationError({
                    'company_ids': f'Solo los propietarios pueden enviar invitaciones. No eres owner de {company.display_name}'
                })

        # Validate role exists
        try:
            role = Role.objects.get(id=role_id, is_active=True)
        except Role.DoesNotExist:
            raise serializers.ValidationError({
                'role_id': 'El rol especificado no existe o no está activo'
            })

        # Check if email is already a member of ANY of the companies
        existing_user = User.objects.filter(email=email).first()
        if existing_user:
            for company in companies:
                existing_role = UserRole.objects.filter(
                    user=existing_user,
                    company=company,
                    active=True
                ).exists()

                if existing_role:
                    raise serializers.ValidationError({
                        'email': f'Este usuario ya es miembro de {company.display_name}'
                    })

        # Check for pending invitations that include any of these companies
        for company in companies:
            pending_invitation = TeamInvitation.objects.filter(
                email=email,
                companies=company,
                status='pending'
            ).exists()

            if pending_invitation:
                raise serializers.ValidationError({
                    'email': f'Ya existe una invitación pendiente para este email que incluye {company.display_name}'
                })

        # Store validated objects for use in the view
        attrs['companies'] = companies
        attrs['role'] = role

        return attrs


class TeamInvitationSerializer(serializers.ModelSerializer):
    """
    Serializer for TeamInvitation model
    """
    invited_by_name = serializers.CharField(source='invited_by.get_full_name', read_only=True)
    company_names = serializers.SerializerMethodField(read_only=True)
    role_name = serializers.CharField(source='role.name', read_only=True)

    def get_company_names(self, obj):
        """Get company names for the invitation"""
        return obj.get_company_names()

    class Meta:
        model = TeamInvitation
        fields = [
            'id', 'email', 'status', 'token', 'expires_at', 'accepted_at',
            'created_at', 'updated_at', 'invited_by_name', 'company_names', 'role_name',
            'companies', 'role', 'invited_by'
        ]
        read_only_fields = [
            'id', 'token', 'created_at', 'updated_at', 'invited_by_name',
            'company_names', 'role_name', 'accepted_at'
        ]


class InvitationValidationSerializer(serializers.Serializer):
    """
    Serializer for invitation validation response
    """
    valid = serializers.BooleanField()
    email = serializers.EmailField()
    companies = serializers.ListField(child=serializers.DictField())
    role = serializers.DictField()
    invited_by = serializers.DictField()
    expires_at = serializers.DateTimeField()
    message = serializers.CharField(required=False)