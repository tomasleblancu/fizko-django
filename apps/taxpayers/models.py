from django.db import models
from django.core.validators import RegexValidator
from django.contrib.auth import get_user_model
from django.conf import settings
from cryptography.fernet import Fernet
import base64
import os
from apps.core.models import TimeStampedModel

User = get_user_model()


class TaxPayer(TimeStampedModel):
    """
    Modelo principal del contribuyente con todos los datos obtenidos del SII
    """
    # Relación con la empresa (la empresa es el contexto principal)
    company = models.OneToOneField(
        'companies.Company',
        on_delete=models.CASCADE,
        related_name='taxpayer',
        help_text="Empresa a la que pertenece este contribuyente"
    )
    
    # Identificación básica
    rut = models.CharField(max_length=12, validators=[RegexValidator(r'^\d{7,8}$')])
    dv = models.CharField(max_length=1, validators=[RegexValidator(r'^[0-9Kk]$')])
    tax_id = models.CharField(max_length=20, unique=True, help_text="RUT con formato completo del SII")
    
    # Datos principales del contribuyente (del SII)
    razon_social = models.CharField(max_length=255, help_text="Razón social oficial del SII")
    nombre = models.CharField(max_length=255, blank=True, help_text="Nombre alternativo")
    tipo_contribuyente = models.CharField(max_length=100, blank=True, help_text="Ej: PERSONA JURIDICA COMERCIAL")
    estado = models.CharField(max_length=50, default='ACTIVO', help_text="Estado en el SII")
    
    # Actividad económica
    actividad_description = models.TextField(blank=True, help_text="Descripción de la actividad económica")
    glosa_actividad = models.TextField(blank=True, help_text="Glosa de la actividad del SII")
    
    # Fechas importantes
    fecha_inicio_actividades = models.DateField(null=True, blank=True)
    
    # Ubicación geográfica (del SII)
    direccion = models.TextField(blank=True, help_text="Dirección completa del SII")
    comuna = models.CharField(max_length=100, blank=True)
    region = models.CharField(max_length=100, blank=True)
    
    # Contacto (del SII)
    email = models.EmailField(blank=True, help_text="Email registrado en SII")
    mobile_phone = models.CharField(max_length=20, blank=True, help_text="Teléfono del SII")
    
    # Metadatos de extracción
    data_source = models.CharField(max_length=50, default='sii_extraction', help_text="Origen de los datos")
    last_sii_sync = models.DateTimeField(null=True, blank=True, help_text="Última sincronización con SII")
    sii_raw_data = models.JSONField(null=True, blank=True, help_text="Datos completos del SII")
    
    # Estado del contribuyente
    is_active = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False, help_text="Verificado contra SII")
    
    class Meta:
        db_table = 'taxpayers'
        verbose_name = 'TaxPayer'
        verbose_name_plural = 'TaxPayers'
        ordering = ['razon_social']
        indexes = [
            models.Index(fields=['rut', 'dv']),
            models.Index(fields=['tax_id']),
            models.Index(fields=['razon_social']),
            models.Index(fields=['estado']),
        ]
    
    def __str__(self):
        return f"{self.razon_social} ({self.tax_id})"
    
    @property
    def full_rut(self):
        """Retorna RUT formateado"""
        if len(self.rut) == 7:
            return f"{self.rut[0]}.{self.rut[1:4]}.{self.rut[4:7]}-{self.dv}"
        elif len(self.rut) == 8:
            return f"{self.rut[0:2]}.{self.rut[2:5]}.{self.rut[5:8]}-{self.dv}"
        return f"{self.rut}-{self.dv}"
    
    @property
    def is_persona_juridica(self):
        """Determina si es persona jurídica basado en el tipo de contribuyente"""
        return 'JURIDICA' in self.tipo_contribuyente.upper() if self.tipo_contribuyente else False
    
    @property
    def formatted_address(self):
        """Dirección formateada con comuna y región"""
        parts = []
        if self.direccion:
            parts.append(self.direccion.strip())
        if self.comuna:
            parts.append(self.comuna)
        if self.region:
            parts.append(self.region)
        return ", ".join(parts)
    
    def sync_from_sii_data(self, sii_data):
        """Actualiza los datos del contribuyente desde los datos del SII y completa modelos relacionados"""
        # Actualizar datos principales del taxpayer
        self.razon_social = sii_data.get('razon_social', '')
        self.nombre = sii_data.get('nombre', '')
        self.tipo_contribuyente = sii_data.get('tipo_contribuyente', '')
        self.estado = sii_data.get('estado', 'ACTIVO')
        self.actividad_description = sii_data.get('actividad_description', '')
        self.glosa_actividad = sii_data.get('glosa_actividad', '')
        self.direccion = sii_data.get('direccion', '')
        self.comuna = sii_data.get('comuna', '')
        self.region = sii_data.get('region', '')
        self.email = sii_data.get('email', '')
        self.mobile_phone = sii_data.get('mobile_phone', '')
        
        # Parsear fecha
        if sii_data.get('fecha_inicio_actividades'):
            try:
                from datetime import datetime
                fecha_str = sii_data['fecha_inicio_actividades']
                if " " in fecha_str:
                    fecha_str = fecha_str.split(" ")[0]
                self.fecha_inicio_actividades = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                pass
        
        # Guardar datos completos
        self.sii_raw_data = sii_data
        self.data_source = sii_data.get('_source', 'sii_extraction')
        self.is_verified = True
        
        from django.utils import timezone
        self.last_sii_sync = timezone.now()
        
        # Guardar el taxpayer primero para tener el ID
        self.save()
        
        # Completar modelos relacionados (se necesita la company para las nuevas relaciones)
        # Nota: Todos los métodos de sync ahora necesitan la company como parámetro
        # La sincronización debe ser llamada desde Company.sync_taxpayer_data()
    
    def _sync_address_from_sii(self, sii_data, company=None):
        """Crea o actualiza la dirección del contribuyente desde datos del SII"""
        if not sii_data.get('direccion') or not company:
            return
            
        from django.apps import apps
        TaxpayerAddress = apps.get_model('taxpayers', 'TaxpayerAddress')
        
        # Buscar dirección existente o crear nueva
        address, created = TaxpayerAddress.objects.update_or_create(
            company=company,
            address_type='legal',  # Dirección legal del SII
            defaults={
                'street_address': sii_data.get('direccion', '').strip(),
                'city': sii_data.get('comuna', '').strip(),
                'region': sii_data.get('region', '').strip(),
                'country': 'Chile',
                'is_primary': True,
                'is_active': True
            }
        )
        
        if created:
            print(f"📍 Nueva dirección creada para {self.tax_id}: {address.street_address}")
        else:
            print(f"📍 Dirección actualizada para {self.tax_id}")
    
    def _sync_activity_from_sii(self, sii_data, company=None):
        """Crea o actualiza la actividad económica del contribuyente desde datos del SII"""
        actividad_desc = sii_data.get('actividad_description') or sii_data.get('glosa_actividad')
        if not actividad_desc or not company:
            return
            
        from django.apps import apps
        TaxpayerActivity = apps.get_model('taxpayers', 'TaxpayerActivity')
        
        # Intentar extraer código de actividad si está disponible (a veces viene en la descripción)
        import re
        code_match = re.search(r'(\d{6})', actividad_desc)
        activity_code = code_match.group(1) if code_match else 'UNKNOWN'
        
        # Crear o actualizar actividad
        activity, created = TaxpayerActivity.objects.update_or_create(
            company=company,
            code=activity_code,
            defaults={
                'description': actividad_desc.strip(),
                'category': self._get_activity_category(actividad_desc),
                'is_active': True
            }
        )
        
        if created:
            print(f"🏢 Nueva actividad creada: {activity_code} - {actividad_desc[:50]}")
        else:
            # Actualizar descripción si es diferente
            if activity.description != actividad_desc.strip():
                activity.description = actividad_desc.strip()
                activity.save()
                print(f"🏢 Actividad actualizada: {activity_code}")
    
    def _get_activity_category(self, descripcion):
        """Categoriza la actividad económica basada en palabras clave"""
        descripcion_lower = descripcion.lower()
        
        # Categorías comunes
        if any(word in descripcion_lower for word in ['comercial', 'venta', 'importación', 'exportación', 'retail']):
            return 'Comercio'
        elif any(word in descripcion_lower for word in ['servicios', 'consultor', 'asesor', 'profesional']):
            return 'Servicios'
        elif any(word in descripcion_lower for word in ['manufactura', 'fabricación', 'industrial', 'producción']):
            return 'Industria'
        elif any(word in descripcion_lower for word in ['construcción', 'inmobiliaria']):
            return 'Construcción'
        elif any(word in descripcion_lower for word in ['tecnología', 'software', 'informática']):
            return 'Tecnología'
        else:
            return 'Otros'

class TaxpayerActivity(TimeStampedModel):
    """
    Actividades económicas del contribuyente
    """
    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.CASCADE,
        related_name='taxpayer_activities',
        help_text="Empresa asociada"
    )
    code = models.CharField(max_length=10)
    description = models.TextField()
    category = models.CharField(max_length=50, blank=True)
    subcategory = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'taxpayer_activities'
        verbose_name = 'Taxpayer Activity'
        verbose_name_plural = 'Taxpayer Activities'
        ordering = ['company', 'code']
        unique_together = ['company', 'code']
    
    def __str__(self):
        return f"{self.code} - {self.description[:50]}"


class TaxpayerAddress(TimeStampedModel):
    """
    Direcciones de contribuyentes
    """
    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.CASCADE,
        related_name='taxpayer_addresses',
        help_text="Empresa asociada"
    )
    address_type = models.CharField(max_length=20, choices=[
        ('commercial', 'Comercial'),
        ('legal', 'Legal'),
        ('postal', 'Postal'),
    ])
    street_address = models.CharField(max_length=500)
    city = models.CharField(max_length=100)
    region = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=10, blank=True)
    country = models.CharField(max_length=50, default='Chile')
    is_primary = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'taxpayer_addresses'
        verbose_name = 'Taxpayer Address'
        verbose_name_plural = 'Taxpayer Addresses'
        ordering = ['company', '-is_primary']
        indexes = [
            models.Index(fields=['company']),
        ]
    
    def __str__(self):
        return f"{self.company.tax_id} - {self.address_type}: {self.street_address[:50]}"
    
    @property
    def full_address(self):
        return f"{self.street_address}, {self.city}, {self.region}, {self.country}"


class TaxpayerPartner(TimeStampedModel):
    """
    Socios de contribuyentes
    """
    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.CASCADE,
        related_name='taxpayer_partners',
        help_text="Empresa asociada"
    )
    partner_rut = models.CharField(max_length=12, validators=[RegexValidator(r'^\d{7,8}$')])
    partner_dv = models.CharField(max_length=1, validators=[RegexValidator(r'^[0-9Kk]$')])
    partner_name = models.CharField(max_length=255)
    partner_type = models.CharField(max_length=50, choices=[
        ('natural', 'Persona Natural'),
        ('juridica', 'Persona Jurídica'),
    ])
    ownership_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    participation_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'taxpayer_partners'
        verbose_name = 'Taxpayer Partner'
        verbose_name_plural = 'Taxpayer Partners'
        ordering = ['company', 'partner_name']
        indexes = [
            models.Index(fields=['company']),
            models.Index(fields=['partner_rut', 'partner_dv']),
        ]
        unique_together = ['company', 'partner_rut', 'partner_dv']
    
    def __str__(self):
        return f"{self.partner_name} ({self.partner_rut}-{self.partner_dv}) - {self.ownership_percentage}%"
    
    @property
    def full_company_rut(self):
        return self.company.tax_id if self.company else ""
    
    @property
    def full_partner_rut(self):
        return f"{self.partner_rut}-{self.partner_dv}"


class TaxpayerRepresentative(TimeStampedModel):
    """
    Representantes legales de contribuyentes
    """
    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.CASCADE,
        related_name='taxpayer_representatives',
        help_text="Empresa asociada"
    )
    representative_rut = models.CharField(max_length=12, validators=[RegexValidator(r'^\d{7,8}$')])
    representative_dv = models.CharField(max_length=1, validators=[RegexValidator(r'^[0-9Kk]$')])
    representative_name = models.CharField(max_length=255)
    position = models.CharField(max_length=100, blank=True)
    appointment_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'taxpayer_representatives'
        verbose_name = 'Taxpayer Representative'
        verbose_name_plural = 'Taxpayer Representatives'
        ordering = ['company', 'representative_name']
        indexes = [
            models.Index(fields=['company']),
            models.Index(fields=['representative_rut', 'representative_dv']),
        ]
        unique_together = ['company', 'representative_rut', 'representative_dv']
    
    def __str__(self):
        return f"{self.representative_name} - {self.position} ({self.representative_rut}-{self.representative_dv})"
    
    @property
    def full_company_rut(self):
        return self.company.tax_id if self.company else ""
    
    @property
    def full_representative_rut(self):
        return f"{self.representative_rut}-{self.representative_dv}"
    
    @property
    def is_valid(self):
        """Verifica si la representación está vigente"""
        if self.expiry_date:
            from datetime import date
            return date.today() <= self.expiry_date
        return self.is_active


class TaxpayerStamp(TimeStampedModel):
    """
    Timbres autorizados por el SII para facturación electrónica
    """
    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.CASCADE,
        related_name='taxpayer_stamps',
        help_text="Empresa asociada"
    )
    stamp_id = models.CharField(max_length=50, unique=True)
    certificate_serial = models.CharField(max_length=100)
    certificate_subject = models.TextField()
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField()
    stamp_type = models.CharField(max_length=20, choices=[
        ('production', 'Producción'),
        ('certification', 'Certificación'),
    ], default='production')
    document_types = models.JSONField(default=list, help_text="Tipos de documentos autorizados")
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'taxpayer_stamps'
        verbose_name = 'Taxpayer Stamp'
        verbose_name_plural = 'Taxpayer Stamps'
        ordering = ['company', '-valid_until']
        indexes = [
            models.Index(fields=['company']),
            models.Index(fields=['valid_until']),
        ]
    
    def __str__(self):
        return f"{self.company.tax_id} - Timbre {self.stamp_id}"
    
    @property
    def full_company_rut(self):
        return self.company.tax_id if self.company else ""
    
    @property
    def is_valid(self):
        """Verifica si el timbre está vigente"""
        from datetime import datetime
        now = datetime.now()
        return self.valid_from <= now <= self.valid_until and self.is_active
    
    @property
    def days_until_expiry(self):
        """Días hasta el vencimiento del timbre"""
        from datetime import datetime
        now = datetime.now()
        if self.valid_until > now:
            return (self.valid_until - now).days
        return 0


class TaxpayerSiiCredentials(TimeStampedModel):
    """
    Credenciales encriptadas del SII para cada contribuyente
    Asociadas a la empresa y al usuario que las registró
    """
    company = models.OneToOneField(
        'companies.Company', 
        on_delete=models.CASCADE,
        related_name='taxpayer_sii_credentials',
        help_text="Empresa asociada a estas credenciales"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        help_text="Usuario que registró estas credenciales"
    )
    tax_id = models.CharField(max_length=20, help_text="RUT del contribuyente")
    encrypted_password = models.TextField(help_text="Contraseña del SII encriptada")
    is_active = models.BooleanField(default=True)
    last_verified = models.DateTimeField(null=True, blank=True, help_text="Última verificación exitosa")
    verification_failures = models.IntegerField(default=0, help_text="Contador de fallos de verificación")
    
    class Meta:
        db_table = 'taxpayer_sii_credentials'
        verbose_name = 'Taxpayer SII Credentials'
        verbose_name_plural = 'Taxpayer SII Credentials'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tax_id']),
            models.Index(fields=['company']),
            models.Index(fields=['user']),
        ]
    
    def __str__(self):
        return f"SII Credentials for {self.tax_id} (User: {self.user.username})"
    
    @staticmethod
    def _get_encryption_key():
        """Obtiene la clave de encriptación desde settings o genera una nueva"""
        from django.conf import settings
        import hashlib
        
        key = getattr(settings, 'SII_ENCRYPTION_KEY', None)
        if not key:
            # Generar clave desde SECRET_KEY si no está configurada
            hash_key = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
            key = base64.urlsafe_b64encode(hash_key)
        else:
            key = key.encode() if isinstance(key, str) else key
        return key
    
    def set_password(self, password):
        """Encripta y almacena la contraseña"""
        if not password:
            raise ValueError("Password cannot be empty")
            
        key = self._get_encryption_key()
        fernet = Fernet(key)
        encrypted = fernet.encrypt(password.encode())
        self.encrypted_password = base64.urlsafe_b64encode(encrypted).decode()
    
    def get_password(self):
        """Desencripta y retorna la contraseña"""
        if not self.encrypted_password:
            return None
            
        try:
            key = self._get_encryption_key()
            fernet = Fernet(key)
            encrypted_bytes = base64.urlsafe_b64decode(self.encrypted_password.encode())
            decrypted = fernet.decrypt(encrypted_bytes)
            return decrypted.decode()
        except Exception as e:
            raise ValueError(f"Error al desencriptar contraseña: {str(e)}")
    
    def verify_credentials(self):
        """Verifica las credenciales contra el SII"""
        try:
            from apps.sii.services import create_sii_service
            password = self.get_password()
            
            sii_service = create_sii_service(
                tax_id=self.tax_id, 
                password=password, 
                use_real=True
            )
            
            try:
                result = sii_service.authenticate()
                if result:
                    from django.utils import timezone
                    self.last_verified = timezone.now()
                    self.verification_failures = 0
                    self.save()
                    return True
                else:
                    self.verification_failures += 1
                    self.save()
                    return False
            finally:
                if hasattr(sii_service, 'close'):
                    sii_service.close()
                    
        except Exception as e:
            self.verification_failures += 1
            self.save()
            raise e
    
    @property
    def is_credentials_valid(self):
        """Indica si las credenciales están activas y no han fallado mucho"""
        return self.is_active and self.verification_failures < 3
