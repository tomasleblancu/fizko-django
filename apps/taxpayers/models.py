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
    Modelo simplificado del contribuyente
    """
    # Relación con la empresa (la empresa es el contexto principal)
    company = models.OneToOneField(
        'companies.Company',
        on_delete=models.CASCADE,
        related_name='taxpayer',
        help_text="Empresa a la que pertenece este contribuyente"
    )

    # Identificación básica
    rut = models.CharField(max_length=12, blank=True, default='')
    dv = models.CharField(max_length=1, blank=True, default='')
    tax_id = models.CharField(max_length=20, unique=True, help_text="RUT con formato completo del SII")

    # Datos básicos del contribuyente
    razon_social = models.CharField(max_length=255, blank=True, default='')

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
        ]
    
    def __str__(self):
        return f"{self.razon_social} ({self.tax_id})"
    
    @property
    def full_rut(self):
        """Retorna RUT formateado"""
        if self.rut and self.dv:
            if len(self.rut) == 7:
                return f"{self.rut[0]}.{self.rut[1:4]}.{self.rut[4:7]}-{self.dv}"
            elif len(self.rut) == 8:
                return f"{self.rut[0:2]}.{self.rut[2:5]}.{self.rut[5:8]}-{self.dv}"
            return f"{self.rut}-{self.dv}"
        return self.tax_id
    
    def sync_from_sii_data(self, sii_data):
        """Actualiza los datos del contribuyente desde los datos del SII"""
        # Actualizar datos básicos
        self.razon_social = sii_data.get('razon_social', '')

        # Extraer RUT y DV del tax_id si están disponibles
        if self.tax_id and '-' in self.tax_id:
            rut_parts = self.tax_id.split('-')
            self.rut = rut_parts[0].replace('.', '')
            self.dv = rut_parts[1]

        # Guardar datos completos
        self.sii_raw_data = sii_data
        self.data_source = sii_data.get('_source', 'sii_extraction')
        self.is_verified = True

        from django.utils import timezone
        self.last_sii_sync = timezone.now()

        # Guardar cambios
        self.save()


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
