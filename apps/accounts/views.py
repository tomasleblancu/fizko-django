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
from django.utils import timezone

from .models import User, UserProfile, Role, UserRole, VerificationCode, TeamInvitation
from .serializers import (
    UserSerializer, UserProfileSerializer, RoleSerializer,
    UserRoleSerializer, CustomTokenObtainPairSerializer,
    UserRegistrationSerializer, ChangePasswordSerializer,
    ProfileUpdateSerializer, SendVerificationCodeSerializer,
    VerifyCodeSerializer, ResendVerificationCodeSerializer,
    InviteToTeamSerializer, InvitationValidationSerializer
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

        # Check if user was created with an invitation
        invitation = getattr(user, '_invitation', None)
        skip_onboarding = invitation is not None

        # Create user profile
        UserProfile.objects.create(
            user=user,
            skip_onboarding=skip_onboarding
        )

        # If there's an invitation, accept it
        invitation_result = None
        if invitation:
            try:
                invitation_result = invitation.accept(user)
                company_names = ', '.join([c['name'] for c in invitation_result['companies']])
                invitation_message = f'Te has unido exitosamente a {company_names} como {invitation_result["role"]["name"]}.'
            except Exception as e:
                # Log error but don't fail registration
                invitation_message = f'Se registró tu cuenta pero hubo un error al procesar la invitación: {str(e)}'
                print(f"Error accepting invitation during registration: {e}")
        else:
            invitation_message = None

        # Note: Verification codes will be generated and sent later when user accesses verification page
        # This prevents sending codes immediately during registration

        response_data = {
            'user': UserSerializer(user).data,
            'message': 'Usuario registrado exitosamente. Por favor inicia sesión para continuar.',
            'next_step': 'login',
            'verification_required': {
                'email': not user.email_verified,
                'phone': not user.phone_verified
            },
            'skip_onboarding': skip_onboarding
        }

        if invitation_message:
            response_data['invitation_message'] = invitation_message

        # Include detailed invitation result if available
        if invitation_result:
            response_data['invitation_result'] = {
                'companies': invitation_result['companies'],
                'role': invitation_result['role'],
                'total_companies': invitation_result['total_companies'],
                'new_roles_created': invitation_result['new_roles_created'],
                'summary': f"Agregado a {invitation_result['total_companies']} empresa(s) como {invitation_result['role']['name']}"
            }

        return Response(response_data, status=status.HTTP_201_CREATED)

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
        try:
            from apps.whatsapp.services import WhatsAppService
            whatsapp_service = WhatsAppService()
            message = f"Tu código de verificación para Fizko es: {code}\n\nEste código expira en 15 minutos."

            # Format phone number for WhatsApp (add + prefix)
            phone_formatted = f"+{user.phone}"

            whatsapp_service.send_message(phone_formatted, message)
        except ImportError:
            # WhatsApp service not available
            print(f"WhatsApp service not available for phone verification to {user.phone}")
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

    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def invite_to_team(self, request):
        """
        Invite a user to join multiple company teams
        Only company owners can send invitations
        """
        serializer = InviteToTeamSerializer(data=request.data, context={'user': request.user})
        serializer.is_valid(raise_exception=True)

        # Extract validated data
        email = serializer.validated_data['email']
        companies = serializer.validated_data['companies']
        role = serializer.validated_data['role']

        try:
            # Create the invitation
            with transaction.atomic():
                invitation = TeamInvitation.objects.create(
                    email=email,
                    role=role,
                    invited_by=request.user,
                    status='pending'
                )
                # Asociar todas las empresas usando ManyToMany
                invitation.companies.set(companies)

            # Send invitation email (optional - could be implemented later)
            self._send_invitation_email(invitation)

            # Create response with multiple companies
            company_data = [
                {
                    'id': company.id,
                    'name': company.display_name,
                    'business_name': company.business_name
                } for company in companies
            ]

            company_names = ', '.join([c.display_name for c in companies])

            return Response({
                'message': f'Invitación enviada exitosamente a {email} para {company_names}',
                'invitation': {
                    'id': invitation.id,
                    'token': str(invitation.token),
                    'email': invitation.email,
                    'companies': company_data,
                    'role': {
                        'id': role.id,
                        'name': role.name
                    },
                    'expires_at': invitation.expires_at,
                    'status': invitation.status
                }
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response(
                {'error': f'Error al crear la invitación: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

    def _send_invitation_email(self, invitation):
        """Send invitation email to the invited user"""
        from django.core.mail import send_mail
        from django.conf import settings
        import logging

        logger = logging.getLogger(__name__)

        # Create invitation link using configured frontend URL
        frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:8080')
        invitation_link = f"{frontend_url}/accept-invitation/{invitation.token}"

        # Format company names with proper grammar
        companies = list(invitation.companies.all())
        company_count = len(companies)

        if company_count == 1:
            # Single company
            company_text = companies[0].display_name
            empresas_text = "la empresa"
        elif company_count == 2:
            # Two companies: "A y B"
            company_text = f"{companies[0].display_name} y {companies[1].display_name}"
            empresas_text = "las empresas"
        else:
            # Multiple companies: "A, B y C"
            company_names = [c.display_name for c in companies]
            company_text = f"{', '.join(company_names[:-1])} y {company_names[-1]}"
            empresas_text = "las empresas"

        # Create subject with proper formatting
        subject = f"Invitación para unirte a {company_text} en Fizko"

        # Create professional email template
        message = f"""
Hola,

{invitation.invited_by.get_full_name()} te ha invitado a unirte a {empresas_text} {company_text} en Fizko como {invitation.role.name}.

Fizko es una plataforma integral de gestión contable y tributaria diseñada específicamente para pequeñas empresas chilenas. Al aceptar esta invitación, tendrás acceso a:

• Automatización de procesos contables y tributarios
• Integración directa con el SII (Servicio de Impuestos Internos)
• Gestión de documentos electrónicos (DTEs)
• Análisis financiero en tiempo real
• Asistente de IA especializado en normativa chilena

Para aceptar la invitación y comenzar a usar Fizko, haz clic en el siguiente enlace:

{invitation_link}

📋 Detalles de la invitación:
• Rol: {invitation.role.name}
• {"Empresa" if company_count == 1 else "Empresas"}: {company_text}
• Invitado por: {invitation.invited_by.get_full_name()}
• Válida hasta: {invitation.expires_at.strftime('%d/%m/%Y a las %H:%M')} (horario de Chile)

Si tienes alguna pregunta sobre esta invitación, puedes contactar directamente a {invitation.invited_by.get_full_name()} en {invitation.invited_by.email}.

Si no solicitaste esta invitación, puedes ignorar este mensaje de forma segura.

¡Bienvenido al futuro de la contabilidad chilena!

Saludos cordiales,
Equipo Fizko
        """

        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [invitation.email],
                fail_silently=False,
            )
            logger.info(f"Invitation email sent successfully to {invitation.email} for {company_count} company(ies)")
        except Exception as e:
            # Log error but don't fail invitation creation
            logger.error(f"Error sending invitation email: {e}")
            print(f"Error sending invitation email: {e}")


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
        """Get users and roles for one or more companies (comma-separated IDs)"""
        company_param = request.query_params.get('company')
        if not company_param:
            return Response(
                {'error': 'company parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Parse company IDs (handle both single ID and comma-separated IDs)
        try:
            if ',' in company_param:
                # Multiple company IDs
                company_ids = [int(id.strip()) for id in company_param.split(',') if id.strip()]
            else:
                # Single company ID
                company_ids = [int(company_param)]
        except ValueError:
            return Response(
                {'error': 'Invalid company ID format'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if user has permission to view all requested companies
        user_company_ids = UserRole.objects.filter(
            user=request.user,
            active=True
        ).values_list('company_id', flat=True)

        # Filter to only companies the user has access to
        accessible_company_ids = [cid for cid in company_ids if cid in user_company_ids]

        if not accessible_company_ids:
            return Response(
                {'error': 'No tienes permiso para ver estas empresas'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Fetch user roles for all accessible companies
        user_roles = UserRole.objects.filter(
            company_id__in=accessible_company_ids,
            active=True
        ).select_related('user', 'company', 'role')

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
        """Send WhatsApp verification code directly via Kapso API (bypass supervisor)"""
        try:
            import requests
            from django.conf import settings
            import logging

            logger = logging.getLogger(__name__)

            # Get Kapso configuration directly from settings
            api_token = getattr(settings, 'KAPSO_API_TOKEN', None)
            whatsapp_config_id = getattr(settings, 'WHATSAPP_CONFIG_ID', None)
            base_url = getattr(settings, 'KAPSO_API_BASE_URL', 'https://app.kapso.ai/api/v1')

            if not api_token:
                logger.error("KAPSO_API_TOKEN not configured - cannot send WhatsApp verification")
                print(f"WhatsApp verification failed: KAPSO_API_TOKEN not configured")
                return

            if not whatsapp_config_id:
                logger.error("WHATSAPP_CONFIG_ID not configured - cannot send WhatsApp verification")
                print(f"WhatsApp verification failed: WHATSAPP_CONFIG_ID not configured")
                return

            # Format phone number for WhatsApp (add + prefix)
            phone_formatted = f"+{user.phone}"

            # Verification message
            message = f"Tu código de verificación para Fizko es: {code}\n\nEste código expira en 15 minutos."

            logger.info(f"🚀 Sending WhatsApp verification code directly via Kapso API to {phone_formatted}")

            headers = {
                'X-API-Key': api_token,
                'Content-Type': 'application/json'
            }

            # Use direct message endpoint (like template messages but for text)
            logger.info(f"📞 Sending WhatsApp verification directly via /whatsapp/messages to {phone_formatted}")

            # Try the direct message endpoint used by templates
            message_payload = {
                'whatsapp_config_id': whatsapp_config_id,
                'phone_number': phone_formatted,
                'message_type': 'text',
                'message': {
                    'content': message
                }
            }

            message_response = requests.post(
                f'{base_url}/whatsapp/messages',
                headers=headers,
                json=message_payload,
                timeout=30
            )

            if message_response.status_code in [200, 201]:
                result = message_response.json()
                logger.info(f"✅ WhatsApp verification sent successfully to {phone_formatted}")
                print(f"WhatsApp verification sent successfully via Kapso direct endpoint to {phone_formatted}")
                return
            else:
                error_msg = f"Failed to send message: {message_response.status_code} - {message_response.text[:200]}"
                logger.error(f"❌ {error_msg}")
                print(f"Error sending WhatsApp message: {error_msg}")

                # Log the response for debugging
                logger.error(f"Response body: {message_response.text}")
                logger.error(f"Request payload: {message_payload}")

        except requests.exceptions.Timeout:
            error_msg = "Timeout conectando con Kapso API"
            logger.error(f"❌ {error_msg}")
            print(f"Error sending WhatsApp verification: {error_msg}")
        except ImportError as e:
            logger.error(f"Import error in WhatsApp verification: {e}")
            print(f"Requests library not available for phone verification to {user.phone}")
        except Exception as e:
            logger.error(f"Unexpected error in WhatsApp verification: {e}")
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
        """Send WhatsApp verification code directly via Kapso API (bypass supervisor)"""
        try:
            import requests
            from django.conf import settings
            import logging

            logger = logging.getLogger(__name__)

            # Get Kapso configuration directly from settings
            api_token = getattr(settings, 'KAPSO_API_TOKEN', None)
            whatsapp_config_id = getattr(settings, 'WHATSAPP_CONFIG_ID', None)
            base_url = getattr(settings, 'KAPSO_API_BASE_URL', 'https://app.kapso.ai/api/v1')

            if not api_token:
                logger.error("KAPSO_API_TOKEN not configured - cannot send WhatsApp verification")
                print(f"WhatsApp verification failed: KAPSO_API_TOKEN not configured")
                return

            if not whatsapp_config_id:
                logger.error("WHATSAPP_CONFIG_ID not configured - cannot send WhatsApp verification")
                print(f"WhatsApp verification failed: WHATSAPP_CONFIG_ID not configured")
                return

            # Format phone number for WhatsApp (add + prefix)
            phone_formatted = f"+{user.phone}"

            # Verification message
            message = f"Tu código de verificación para Fizko es: {code}\n\nEste código expira en 15 minutos."

            logger.info(f"🚀 Sending WhatsApp verification code directly via Kapso API to {phone_formatted}")

            headers = {
                'X-API-Key': api_token,
                'Content-Type': 'application/json'
            }

            # Use direct message endpoint (like template messages but for text)
            logger.info(f"📞 Sending WhatsApp verification directly via /whatsapp/messages to {phone_formatted}")

            # Try the direct message endpoint used by templates
            message_payload = {
                'whatsapp_config_id': whatsapp_config_id,
                'phone_number': phone_formatted,
                'message_type': 'text',
                'message': {
                    'content': message
                }
            }

            message_response = requests.post(
                f'{base_url}/whatsapp/messages',
                headers=headers,
                json=message_payload,
                timeout=30
            )

            if message_response.status_code in [200, 201]:
                result = message_response.json()
                logger.info(f"✅ WhatsApp verification sent successfully to {phone_formatted}")
                print(f"WhatsApp verification sent successfully via Kapso direct endpoint to {phone_formatted}")
                return
            else:
                error_msg = f"Failed to send message: {message_response.status_code} - {message_response.text[:200]}"
                logger.error(f"❌ {error_msg}")
                print(f"Error sending WhatsApp message: {error_msg}")

                # Log the response for debugging
                logger.error(f"Response body: {message_response.text}")
                logger.error(f"Request payload: {message_payload}")

        except requests.exceptions.Timeout:
            error_msg = "Timeout conectando con Kapso API"
            logger.error(f"❌ {error_msg}")
            print(f"Error sending WhatsApp verification: {error_msg}")
        except ImportError as e:
            logger.error(f"Import error in WhatsApp verification: {e}")
            print(f"Requests library not available for phone verification to {user.phone}")
        except Exception as e:
            logger.error(f"Unexpected error in WhatsApp verification: {e}")
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


class InvitationValidationView(APIView):
    """
    API view for validating team invitations
    """
    permission_classes = []  # Public endpoint

    def get(self, request, token):
        """Validate invitation token and return invitation details"""
        try:
            # Parse UUID token
            import uuid
            try:
                token_uuid = uuid.UUID(token)
            except ValueError:
                return Response({
                    'valid': False,
                    'message': 'Token de invitación inválido'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Find invitation
            try:
                invitation = TeamInvitation.objects.select_related(
                    'role', 'invited_by'
                ).prefetch_related('companies').get(token=token_uuid, status='pending')
            except TeamInvitation.DoesNotExist:
                return Response({
                    'valid': False,
                    'message': 'Invitación no encontrada'
                }, status=status.HTTP_404_NOT_FOUND)

            # Check if invitation is still valid
            if not invitation.can_be_accepted():
                return Response({
                    'valid': False,
                    'message': 'La invitación ha expirado'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Return invitation details
            data = {
                'valid': True,
                'email': invitation.email,
                'companies': [
                    {
                        'id': company.id,
                        'name': company.display_name,
                        'business_name': company.business_name,
                        'tax_id': company.tax_id
                    } for company in invitation.companies.all()
                ],
                'role': {
                    'id': invitation.role.id,
                    'name': invitation.role.name,
                    'description': invitation.role.description
                },
                'invited_by': {
                    'id': invitation.invited_by.id,
                    'name': invitation.invited_by.get_full_name(),
                    'email': invitation.invited_by.email
                },
                'expires_at': invitation.expires_at,
            }

            # Generate message with company names
            company_names = ', '.join([c.display_name for c in invitation.companies.all()])
            data['message'] = f'Te han invitado a unirte a {company_names} como {invitation.role.name}'

            serializer = InvitationValidationSerializer(data)
            return Response(serializer.data)

        except Exception as e:
            return Response({
                'valid': False,
                'message': 'Error interno del servidor'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)