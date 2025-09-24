from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.accounts.models import Role, UserRole
from apps.companies.models import Company
from apps.taxpayers.models import TaxpayerSiiCredentials


User = get_user_model()


class Command(BaseCommand):
    help = 'Diagnostica y repara problemas de roles de usuario'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user-email',
            type=str,
            help='Email del usuario específico a diagnosticar'
        )
        parser.add_argument(
            '--company-id',
            type=int,
            help='ID de la empresa específica a diagnosticar'
        )
        parser.add_argument(
            '--repair',
            action='store_true',
            help='Reparar roles faltantes o inactivos encontrados'
        )
        parser.add_argument(
            '--create-missing-roles',
            action='store_true',
            help='Crear roles por defecto si no existen'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("🔍 Iniciando diagnóstico de roles de usuario...\n"))

        # Crear roles por defecto si no existen
        if options['create_missing_roles']:
            self.create_default_roles()

        # Diagnosticar usuarios específicos o todos
        if options['user_email']:
            try:
                user = User.objects.get(email=options['user_email'])
                self.diagnose_user(user, options.get('company_id'), options['repair'])
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"❌ Usuario {options['user_email']} no encontrado"))
        else:
            self.diagnose_all_users(options.get('company_id'), options['repair'])

        self.stdout.write(self.style.SUCCESS("\n✅ Diagnóstico completado"))

    def create_default_roles(self):
        """Crear roles por defecto si no existen"""
        self.stdout.write("📋 Verificando roles por defecto...")

        default_roles = [
            {
                'name': 'owner',
                'description': 'Propietario de la empresa con acceso completo',
                'permissions': {
                    'companies': ['view', 'edit', 'delete', 'manage_users'],
                    'documents': ['view', 'create', 'edit', 'delete'],
                    'forms': ['view', 'create', 'edit', 'submit'],
                    'analytics': ['view', 'export'],
                    'settings': ['view', 'edit'],
                    'users': ['view', 'invite', 'edit', 'remove'],
                    'billing': ['view', 'edit']
                }
            },
            {
                'name': 'admin',
                'description': 'Administrador con permisos amplios pero limitados',
                'permissions': {
                    'companies': ['view', 'edit'],
                    'documents': ['view', 'create', 'edit', 'delete'],
                    'forms': ['view', 'create', 'edit', 'submit'],
                    'analytics': ['view', 'export'],
                    'settings': ['view'],
                    'users': ['view', 'invite']
                }
            },
            {
                'name': 'user',
                'description': 'Usuario básico con permisos de solo lectura/uso',
                'permissions': {
                    'companies': ['view'],
                    'documents': ['view', 'create'],
                    'forms': ['view', 'create', 'submit'],
                    'analytics': ['view'],
                    'settings': ['view'],
                    'users': ['view']
                }
            }
        ]

        for role_data in default_roles:
            role, created = Role.objects.get_or_create(
                name=role_data['name'],
                defaults={
                    'description': role_data['description'],
                    'permissions': role_data['permissions'],
                    'is_active': True
                }
            )
            status = "creado" if created else "ya existe"
            self.stdout.write(f"  ✅ Rol '{role.name}': {status}")

    def diagnose_all_users(self, company_id=None, repair=False):
        """Diagnosticar todos los usuarios"""
        users = User.objects.all()

        if company_id:
            # Solo usuarios que tienen credenciales SII para esa empresa
            users = users.filter(
                taxpayersiicredentials__company_id=company_id
            ).distinct()

        self.stdout.write(f"👥 Diagnosticando {users.count()} usuarios...\n")

        problems_found = 0
        for user in users:
            user_problems = self.diagnose_user(user, company_id, repair, verbose=False)
            problems_found += user_problems

        self.stdout.write(f"\n📊 Resumen: {problems_found} problemas encontrados en total")

    def diagnose_user(self, user, company_id=None, repair=False, verbose=True):
        """Diagnosticar un usuario específico"""
        if verbose:
            self.stdout.write(f"\n👤 Diagnosticando usuario: {user.email}")

        problems_found = 0

        # Obtener empresas asociadas al usuario
        if company_id:
            companies = Company.objects.filter(id=company_id)
        else:
            companies = Company.objects.filter(
                taxpayer_sii_credentials__user=user
            ).distinct()

        if not companies.exists():
            if verbose:
                self.stdout.write(f"  ℹ️ Usuario no tiene empresas asociadas")
            return problems_found

        for company in companies:
            if verbose:
                self.stdout.write(f"  🏢 Empresa: {company.business_name or company.tax_id} (ID: {company.id})")

            # Verificar si tiene credenciales SII
            has_credentials = TaxpayerSiiCredentials.objects.filter(
                user=user,
                company=company,
                is_active=True
            ).exists()

            if verbose:
                cred_status = "✅" if has_credentials else "❌"
                self.stdout.write(f"    Credenciales SII: {cred_status}")

            # Verificar roles
            user_roles = UserRole.objects.filter(
                user=user,
                company=company
            )

            active_roles = user_roles.filter(active=True)
            inactive_roles = user_roles.filter(active=False)

            if verbose:
                self.stdout.write(f"    Roles activos: {active_roles.count()}")
                self.stdout.write(f"    Roles inactivos: {inactive_roles.count()}")

            # Problemas detectados
            if has_credentials and not active_roles.exists():
                problems_found += 1
                if verbose:
                    self.stdout.write(f"    ❌ PROBLEMA: Usuario con credenciales SII pero sin roles activos")

                if repair:
                    self.repair_missing_role(user, company, verbose)

            if inactive_roles.exists():
                problems_found += len(inactive_roles)
                if verbose:
                    self.stdout.write(f"    ⚠️ PROBLEMA: {inactive_roles.count()} roles inactivos")

                if repair:
                    self.repair_inactive_roles(user, company, inactive_roles, verbose)

            # Mostrar roles actuales
            if verbose and active_roles.exists():
                for user_role in active_roles:
                    self.stdout.write(f"    ✅ Rol activo: {user_role.role.name}")

        return problems_found

    def repair_missing_role(self, user, company, verbose=True):
        """Reparar rol faltante para usuario con credenciales SII"""
        try:
            # Determinar qué rol asignar
            existing_owners = UserRole.objects.filter(
                company=company,
                role__name='owner',
                active=True
            ).count()

            role_name = 'owner' if existing_owners == 0 else 'admin'

            owner_role = Role.objects.get(name=role_name)
            user_role, created = UserRole.objects.get_or_create(
                user=user,
                company=company,
                role=owner_role,
                defaults={'active': True}
            )

            if not user_role.active:
                user_role.active = True
                user_role.save()

            if verbose:
                action = "creado" if created else "activado"
                self.stdout.write(f"    🔧 REPARADO: Rol '{role_name}' {action}")

        except Exception as e:
            if verbose:
                self.stdout.write(f"    ❌ Error reparando rol: {str(e)}")

    def repair_inactive_roles(self, user, company, inactive_roles, verbose=True):
        """Reparar roles inactivos"""
        for user_role in inactive_roles:
            user_role.active = True
            user_role.save()

            if verbose:
                self.stdout.write(f"    🔧 REPARADO: Rol '{user_role.role.name}' activado")

    def get_role_summary(self):
        """Obtener resumen de roles en el sistema"""
        self.stdout.write("\n📋 Resumen de roles en el sistema:")

        roles = Role.objects.all()
        for role in roles:
            active_assignments = UserRole.objects.filter(role=role, active=True).count()
            inactive_assignments = UserRole.objects.filter(role=role, active=False).count()

            self.stdout.write(f"  • {role.name}: {active_assignments} activos, {inactive_assignments} inactivos")