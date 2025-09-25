"""
Views for the accounts app - User management and authentication
"""
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.db import transaction

from .models import User, UserProfile, Role, UserRole, VerificationCode
from .serializers import (
    UserSerializer, UserProfileSerializer, RoleSerializer,
    UserRoleSerializer, CustomTokenObtainPairSerializer,
    UserRegistrationSerializer, ChangePasswordSerializer,
    ProfileUpdateSerializer, SendVerificationCodeSerializer,
    VerifyCodeSerializer, ResendVerificationCodeSerializer
)
from apps.core.permissions import IsOwnerOrReadOnly, IsCompanyMember


class CurrentUserView(APIView):
    """
    View to get current authenticated user information
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Get current user profile"""
        serializer = UserSerializer(request.user)
        return Response(serializer.data)


class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Custom login view that returns user data along with tokens
    """
    serializer_class = CustomTokenObtainPairSerializer


class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing users
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        """Return different serializers based on action"""
        if self.action == 'create':
            return UserRegistrationSerializer
        elif self.action == 'change_password':
            return ChangePasswordSerializer
        elif self.action in ['update', 'partial_update'] and hasattr(self.request.user, 'profile'):
            return ProfileUpdateSerializer
        return UserSerializer
    
    def get_permissions(self):
        """Set permissions based on action"""
        if self.action == 'create':
            # Anyone can register
            return []
        elif self.action in ['update', 'partial_update', 'destroy']:
            # Only owner can modify their own profile
            return [permissions.IsAuthenticated(), IsOwnerOrReadOnly()]
        return [permissions.IsAuthenticated()]
    
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """Create new user with profile and send verification codes"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Create user profile
        UserProfile.objects.create(user=user)

        # Generate verification codes
        email_code = VerificationCode.create_verification_code(user, 'email')
        phone_code = VerificationCode.create_verification_code(user, 'phone')

        # Send verification codes
        self._send_email_verification(user, email_code.code)
        self._send_phone_verification(user, phone_code.code)

        return Response({
            'user': UserSerializer(user).data,
            'message': 'Usuario registrado. Por favor verifica tu email y teléfono.',
            'next_step': 'verification',
            'verification_required': {
                'email': not user.email_verified,
                'phone': not user.phone_verified
            }
        }, status=status.HTTP_201_CREATED)

    def _send_email_verification(self, user, code):
        """Send email verification code"""
        from django.core.mail import send_mail
        from django.conf import settings
        import logging

        logger = logging.getLogger(__name__)

        subject = f"Código de verificación Fizko: {code}"
        message = f"""
        Hola {user.first_name},

        Tu código de verificación para Fizko es: {code}

        Este código expira en 15 minutos.

        Si no solicitaste este código, puedes ignorar este mensaje.

        Saludos,
        Equipo Fizko
        """

        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )
            logger.info(f"Email verification sent successfully to {user.email}")
        except Exception as e:
            # Log error but don't fail registration
            logger.error(f"Error sending email verification: {e}")
            print(f"Error sending email verification: {e}")

    def _send_phone_verification(self, user, code):
        """Send WhatsApp verification code"""
        from apps.whatsapp.services import WhatsAppService

        try:
            whatsapp_service = WhatsAppService()
            message = f"Tu código de verificación para Fizko es: {code}\n\nEste código expira en 15 minutos."

            # Format phone number for WhatsApp (add + prefix)
            phone_formatted = f"+{user.phone}"

            whatsapp_service.send_message(phone_formatted, message)
        except Exception as e:
            # Log error but don't fail registration
            print(f"Error sending WhatsApp verification: {e}")
    
    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def me(self, request):
        """Get current user profile"""
        serializer = UserSerializer(request.user)
        return Response(serializer.data)
    
    @action(detail=False, methods=['put'], permission_classes=[permissions.IsAuthenticated])
    def update_profile(self, request):
        """Update current user profile"""
        serializer = ProfileUpdateSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserSerializer(user).data)
    
    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def change_password(self, request):
        """Change user password"""
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        if not user.check_password(serializer.validated_data['old_password']):
            return Response(
                {'old_password': 'Contraseña actual incorrecta'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user.set_password(serializer.validated_data['new_password'])
        user.save()
        
        return Response({'message': 'Contraseña actualizada exitosamente'})
    
    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def logout(self, request):
        """Logout user by blacklisting refresh token"""
        try:
            refresh_token = request.data.get('refresh')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
            return Response({'message': 'Logout exitoso'})
        except Exception as e:
            return Response(
                {'error': 'Token inválido'},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def companies(self, request, pk=None):
        """Get companies where the user has an active role"""
        try:
            user = self.get_object()

            # Solo permitir que el usuario vea sus propias empresas o ser admin
            if request.user != user and not request.user.is_staff:
                return Response(
                    {'error': 'No tienes permisos para ver las empresas de este usuario'},
                    status=status.HTTP_403_FORBIDDEN
                )

            # Obtener empresas donde el usuario tiene roles activos
            user_roles = UserRole.objects.filter(
                user=user,
                active=True
            ).select_related('company', 'role')

            companies_data = []
            for user_role in user_roles:
                company = user_role.company
                companies_data.append({
                    'id': company.id,
                    'name': company.display_name,
                    'display_name': company.display_name,
                    'business_name': company.business_name,
                    'tax_id': company.tax_id,
                    'email': company.email,
                    'role': user_role.role.name,
                    'is_active': user_role.active
                })

            return Response(companies_data)

        except User.DoesNotExist:
            return Response(
                {'error': 'Usuario no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )


class UserProfileViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing user profiles
    """
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]
    
    def get_queryset(self):
        """Users can only access their own profile"""
        return UserProfile.objects.filter(user=self.request.user)


class RoleViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing available roles
    """
    queryset = Role.objects.filter(is_active=True)
    serializer_class = RoleSerializer
    permission_classes = [permissions.IsAuthenticated]


class UserRoleViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing user roles in companies
    """
    queryset = UserRole.objects.all()
    serializer_class = UserRoleSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Filter by company and user permissions"""
        queryset = UserRole.objects.all()
        
        # Filter by company if specified
        company_id = self.request.query_params.get('company', None)
        if company_id:
            queryset = queryset.filter(company_id=company_id)
            
        # Users can see roles for companies they belong to
        user_companies = UserRole.objects.filter(
            user=self.request.user, 
            active=True
        ).values_list('company_id', flat=True)
        
        queryset = queryset.filter(company_id__in=user_companies)
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def my_roles(self, request):
        """Get current user's roles across all companies"""
        user_roles = UserRole.objects.filter(user=request.user, active=True)
        serializer = UserRoleSerializer(user_roles, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_company(self, request):
        """Get users and roles for a specific company"""
        company_id = request.query_params.get('company')
        if not company_id:
            return Response(
                {'error': 'company parameter is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if user has permission to view this company
        if not UserRole.objects.filter(
            user=request.user, 
            company_id=company_id, 
            active=True
        ).exists():
            return Response(
                {'error': 'No tienes permiso para ver esta empresa'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        user_roles = UserRole.objects.filter(company_id=company_id, active=True)
        serializer = UserRoleSerializer(user_roles, many=True)
        return Response(serializer.data)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def debug_user_permissions(request):
    """
    Endpoint de debug para verificar permisos y empresas del usuario
    """
    user = request.user

    # Obtener todas las empresas donde el usuario tiene roles
    user_roles = UserRole.objects.filter(user=user).select_related('company', 'role')

    companies_data = []
    for user_role in user_roles:
        company = user_role.company
        companies_data.append({
            'company_id': company.id,
            'tax_id': company.tax_id,
            'business_name': company.business_name,
            'display_name': company.display_name,
            'role': user_role.role.name,
            'active': user_role.active,
            'created_at': user_role.created_at.isoformat() if user_role.created_at else None
        })

    # Información general del usuario
    debug_info = {
        'user': {
            'id': user.id,
            'email': user.email,
            'is_authenticated': user.is_authenticated,
            'is_verified': getattr(user, 'is_verified', False),
        },
        'companies': companies_data,
        'total_companies': len(companies_data),
        'active_companies': len([c for c in companies_data if c['active']]),
        'available_company_ids': [c['company_id'] for c in companies_data if c['active']]
    }

    return Response(debug_info)


class VerificationView(APIView):
    """
    API views for handling email and phone verification
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        """Verify a code"""
        serializer = VerifyCodeSerializer(data=request.data, context={'user': request.user})
        serializer.is_valid(raise_exception=True)

        verification_code = serializer.validated_data['verification_code']
        verification_type = serializer.validated_data['verification_type']

        # Mark code as used
        verification_code.mark_as_used()

        # Update user verification status
        user = request.user
        if verification_type == 'email':
            user.email_verified = True
        elif verification_type == 'phone':
            user.phone_verified = True

        user.save()

        return Response({
            'message': f'{verification_type.title()} verificado exitosamente',
            'verification_status': {
                'email_verified': user.email_verified,
                'phone_verified': user.phone_verified,
                'fully_verified': user.is_fully_verified
            }
        })


class SendVerificationCodeView(APIView):
    """
    API view for sending verification codes
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        """Send verification code"""
        serializer = SendVerificationCodeSerializer(
            data=request.data,
            context={'user': request.user}
        )
        serializer.is_valid(raise_exception=True)

        verification_type = serializer.validated_data['verification_type']
        user = request.user

        # Create verification code
        verification_code = VerificationCode.create_verification_code(user, verification_type)

        # Send code
        if verification_type == 'email':
            self._send_email_verification(user, verification_code.code)
        elif verification_type == 'phone':
            self._send_phone_verification(user, verification_code.code)

        return Response({
            'message': f'Código de verificación enviado a tu {verification_type}',
            'expires_at': verification_code.expires_at,
            'can_resend_after': 5  # minutes
        })

    def _send_email_verification(self, user, code):
        """Send email verification code"""
        from django.core.mail import send_mail
        from django.conf import settings
        import logging

        logger = logging.getLogger(__name__)

        subject = f"Código de verificación Fizko: {code}"
        message = f"""
        Hola {user.first_name},

        Tu código de verificación para Fizko es: {code}

        Este código expira en 15 minutos.

        Si no solicitaste este código, puedes ignorar este mensaje.

        Saludos,
        Equipo Fizko
        """

        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )
            logger.info(f"Email verification sent successfully to {user.email}")
        except Exception as e:
            # Log error but don't fail registration
            logger.error(f"Error sending email verification: {e}")
            print(f"Error sending email verification: {e}")

    def _send_phone_verification(self, user, code):
        """Send WhatsApp verification code using Kapso service"""
        from apps.chat.services.chat_service import chat_service

        try:
            message = f"Tu código de verificación para Fizko es: {code}\n\nEste código expira en 15 minutos."

            # Format phone number for WhatsApp (add + prefix)
            phone_formatted = f"+{user.phone}"

            result = chat_service.send_message(
                service_type='whatsapp',
                recipient=phone_formatted,
                message=message
            )

            if result.get('status') == 'error':
                print(f"Error sending WhatsApp verification via Kapso: {result.get('error')}")
            else:
                print(f"WhatsApp verification sent successfully via Kapso to {phone_formatted}")

        except Exception as e:
            print(f"Error sending WhatsApp verification: {e}")


class ResendVerificationCodeView(APIView):
    """
    API view for resending verification codes
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        """Resend verification code"""
        serializer = ResendVerificationCodeSerializer(
            data=request.data,
            context={'user': request.user}
        )
        serializer.is_valid(raise_exception=True)

        verification_type = serializer.validated_data['verification_type']
        user = request.user

        # Update last resent time on existing code
        latest_code = VerificationCode.objects.filter(
            user=user,
            verification_type=verification_type
        ).order_by('-created_at').first()

        if latest_code:
            from django.utils import timezone
            latest_code.last_resent_at = timezone.now()
            latest_code.save(update_fields=['last_resent_at'])

        # Create new verification code
        verification_code = VerificationCode.create_verification_code(user, verification_type)

        # Send code
        if verification_type == 'email':
            self._send_email_verification(user, verification_code.code)
        elif verification_type == 'phone':
            self._send_phone_verification(user, verification_code.code)

        return Response({
            'message': f'Nuevo código de verificación enviado a tu {verification_type}',
            'expires_at': verification_code.expires_at,
            'can_resend_after': 5  # minutes
        })

    def _send_email_verification(self, user, code):
        """Send email verification code"""
        from django.core.mail import send_mail
        from django.conf import settings
        import logging

        logger = logging.getLogger(__name__)

        subject = f"Código de verificación Fizko: {code}"
        message = f"""
        Hola {user.first_name},

        Tu código de verificación para Fizko es: {code}

        Este código expira en 15 minutos.

        Si no solicitaste este código, puedes ignorar este mensaje.

        Saludos,
        Equipo Fizko
        """

        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )
            logger.info(f"Email verification sent successfully to {user.email}")
        except Exception as e:
            # Log error but don't fail registration
            logger.error(f"Error sending email verification: {e}")
            print(f"Error sending email verification: {e}")

    def _send_phone_verification(self, user, code):
        """Send WhatsApp verification code using Kapso service"""
        from apps.chat.services.chat_service import chat_service

        try:
            message = f"Tu código de verificación para Fizko es: {code}\n\nEste código expira en 15 minutos."

            # Format phone number for WhatsApp (add + prefix)
            phone_formatted = f"+{user.phone}"

            result = chat_service.send_message(
                service_type='whatsapp',
                recipient=phone_formatted,
                message=message
            )

            if result.get('status') == 'error':
                print(f"Error sending WhatsApp verification via Kapso: {result.get('error')}")
            else:
                print(f"WhatsApp verification sent successfully via Kapso to {phone_formatted}")

        except Exception as e:
            print(f"Error sending WhatsApp verification: {e}")


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def verification_status(request):
    """
    Get current user's verification status
    """
    user = request.user

    return Response({
        'user_id': user.id,
        'email': user.email,
        'phone': user.phone,
        'email_verified': user.email_verified,
        'phone_verified': user.phone_verified,
        'fully_verified': user.is_fully_verified,
        'requires_verification': not user.is_fully_verified
    })