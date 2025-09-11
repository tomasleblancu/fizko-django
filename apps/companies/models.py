from django.db import models
from django.core.validators import RegexValidator
from apps.core.models import TimeStampedModel


class Company(TimeStampedModel):
    """
    Modelo de empresa - solo contiene datos configurables por el usuario.
    Los datos del SII están en el modelo TaxPayer relacionado.
    """
    # Nota: La relación con TaxPayer ahora está en el modelo TaxPayer
    # TaxPayer.company apunta a esta Company
    
    # Identificación básica (duplicada para compatibilidad)
    tax_id = models.CharField(max_length=20, unique=True, help_text="RUT con formato XX.XXX.XXX-X")
    
    # Datos configurables por el usuario en onboarding
    business_name = models.CharField(max_length=255, help_text="Nombre comercial elegido por el usuario")
    display_name = models.CharField(max_length=255, blank=True, help_text="Nombre a mostrar en la aplicación")
    
    # Contacto personalizable por el usuario
    email = models.EmailField(help_text="Email principal de contacto")
    billing_email = models.EmailField(blank=True, help_text="Email para facturación")
    accounting_email = models.EmailField(blank=True, help_text="Email para contabilidad")
    mobile_phone = models.CharField(max_length=20, blank=True, help_text="Teléfono de contacto")
    website = models.URLField(blank=True, help_text="Sitio web de la empresa")
    
    # Configuración de la aplicación
    electronic_biller = models.BooleanField(default=True, help_text="¿Emite documentos electrónicos?")
    preferred_currency = models.CharField(max_length=3, default='CLP', help_text="Moneda preferida")
    time_zone = models.CharField(max_length=50, default='America/Santiago', help_text="Zona horaria")
    
    # Configuración tributaria personalizable
    person_company = models.CharField(
        max_length=50, 
        choices=[
            ('PERSONA', 'Persona Natural'),
            ('EMPRESA', 'Empresa/Persona Jurídica'),
        ],
        default='EMPRESA',
        help_text="Clasificación para la aplicación"
    )
    
    # Configuración de la cuenta
    is_active = models.BooleanField(default=True)
    login_tries = models.IntegerField(default=0)
    logo = models.ImageField(upload_to='companies/logos/', blank=True, null=True)
    
    # Configuración de notificaciones
    notify_new_documents = models.BooleanField(default=True)
    notify_tax_deadlines = models.BooleanField(default=True)
    notify_system_updates = models.BooleanField(default=True)
    
    # Timestamps de registro
    record_created_at = models.DateTimeField(null=True, blank=True)
    record_updated_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'companies'
        verbose_name = 'Company'
        verbose_name_plural = 'Companies'
        ordering = ['business_name']
        
    def __str__(self):
        return f"{self.display_name or self.business_name} ({self.tax_id})"
    
    @property
    def name(self):
        """Nombre a mostrar - compatibilidad con código existente"""
        return self.display_name or self.business_name or (self.taxpayer.razon_social if hasattr(self, 'taxpayer') else '')
    
    @property
    def full_rut(self):
        """Retorna RUT formateado desde el taxpayer"""
        return self.taxpayer.full_rut if hasattr(self, 'taxpayer') else self.tax_id
    
    @property
    def razon_social(self):
        """Razón social oficial del SII"""
        return self.taxpayer.razon_social if hasattr(self, 'taxpayer') else ''
    
    @property
    def sii_address(self):
        """Dirección registrada en el SII"""
        return self.taxpayer.formatted_address if hasattr(self, 'taxpayer') else ''
    
    @property
    def activity_description(self):
        """Descripción de actividad económica del SII"""
        return self.taxpayer.actividad_description if hasattr(self, 'taxpayer') else ''
    
    @property
    def activity_start_date(self):
        """Fecha de inicio de actividades del SII"""
        return self.taxpayer.fecha_inicio_actividades if hasattr(self, 'taxpayer') else None
    
    @property
    def is_verified_with_sii(self):
        """¿Los datos están verificados con el SII?"""
        return self.taxpayer.is_verified if hasattr(self, 'taxpayer') else False
    
    def get_contact_email(self, purpose='general'):
        """Obtiene el email apropiado según el propósito"""
        if purpose == 'billing' and self.billing_email:
            return self.billing_email
        elif purpose == 'accounting' and self.accounting_email:
            return self.accounting_email
        else:
            return self.email
    
    def sync_taxpayer_data(self):
        """Sincroniza algunos datos básicos desde el taxpayer"""
        if hasattr(self, 'taxpayer') and self.taxpayer:
            # Si no tiene display_name, usar la razón social del SII
            if not self.display_name:
                self.display_name = self.taxpayer.razon_social
            
            # Clasificación automática basada en tipo de contribuyente
            if self.taxpayer.is_persona_juridica:
                self.person_company = 'EMPRESA'
            else:
                self.person_company = 'PERSONA'
    
    def get_sii_credentials(self):
        """Obtiene las credenciales del SII almacenadas para esta empresa"""
        try:
            return self.taxpayer_sii_credentials
        except AttributeError:
            return None
    
    def has_sii_credentials(self):
        """Verifica si la empresa tiene credenciales del SII almacenadas"""
        credentials = self.get_sii_credentials()
        return credentials is not None and credentials.is_credentials_valid
    
    def sync_with_sii(self, user=None):
        """Sincroniza los datos de la empresa con el SII usando credenciales almacenadas"""
        if not self.has_sii_credentials():
            raise ValueError("No se encontraron credenciales válidas del SII para esta empresa")
        
        credentials = self.get_sii_credentials()
        
        try:
            from apps.sii.services import create_sii_service
            password = credentials.get_password()
            
            sii_service = create_sii_service(
                tax_id=self.tax_id, 
                password=password, 
                use_real=True
            )
            
            try:
                sii_service.authenticate()
                contribuyente_data = sii_service.consultar_contribuyente()
                
                # Actualizar datos del taxpayer
                if self.taxpayer:
                    self.taxpayer.sync_from_sii_data(contribuyente_data)
                    self.taxpayer.save()
                    
                    # Sincronizar modelos relacionados que necesitan la company
                    self.taxpayer._sync_address_from_sii(contribuyente_data, company=self)
                    self.taxpayer._sync_activity_from_sii(contribuyente_data, company=self)
                
                # Actualizar última verificación de credenciales
                from django.utils import timezone
                credentials.last_verified = timezone.now()
                credentials.verification_failures = 0
                credentials.save()
                
                # Sincronizar algunos datos de la company
                self.sync_taxpayer_data()
                self.save()
                
                return {
                    'status': 'success',
                    'message': 'Sincronización con SII exitosa',
                    'data': contribuyente_data
                }
                
            finally:
                if hasattr(sii_service, 'close'):
                    sii_service.close()
                    
        except Exception as e:
            # Incrementar fallos de verificación
            credentials.verification_failures += 1
            credentials.save()
            
            raise ValueError(f"Error sincronizando con SII: {str(e)}")