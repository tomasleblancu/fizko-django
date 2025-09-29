from django.db import models
from django.core.validators import RegexValidator
from apps.core.models import TimeStampedModel


class Contact(TimeStampedModel):
    """
    Modelo unificado para gestión de contactos (clientes y/o proveedores)
    Un contacto puede ser cliente, proveedor, o ambos
    """
    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.CASCADE,
        related_name='contacts',
        help_text="Empresa propietaria del contacto"
    )

    # Identificación básica - ÚNICO CAMPO OBLIGATORIO
    tax_id = models.CharField(
        max_length=20,
        validators=[RegexValidator(
            regex=r'^\d{1,2}\.\d{3}\.\d{3}-[\dkK]$',
            message='RUT debe tener formato XX.XXX.XXX-X'
        )],
        help_text="RUT con formato XX.XXX.XXX-X"
    )

    # Información opcional
    name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Nombre o razón social del contacto"
    )

    # Información de contacto
    email = models.EmailField(
        blank=True,
        help_text="Email de contacto"
    )

    phone = models.CharField(
        max_length=20,
        blank=True,
        help_text="Teléfono de contacto"
    )

    address = models.TextField(
        blank=True,
        help_text="Dirección"
    )

    # Categoría (útil para proveedores)
    category = models.CharField(
        max_length=100,
        blank=True,
        help_text="Categoría o tipo (ej: Servicios, Productos, etc.)"
    )

    # Roles flexibles - un contacto puede ser ambos
    is_client = models.BooleanField(
        default=False,
        help_text="¿Es cliente?"
    )

    is_provider = models.BooleanField(
        default=False,
        help_text="¿Es proveedor?"
    )

    # Estado y notas
    is_active = models.BooleanField(
        default=True,
        help_text="Contacto activo"
    )

    notes = models.TextField(
        blank=True,
        help_text="Notas adicionales sobre el contacto"
    )

    class Meta:
        db_table = 'contacts_contacts'
        verbose_name = 'Contacto'
        verbose_name_plural = 'Contactos'
        ordering = ['name', 'tax_id']
        unique_together = ['company', 'tax_id']
        indexes = [
            models.Index(fields=['company', 'is_active']),
            models.Index(fields=['company', 'is_client']),
            models.Index(fields=['company', 'is_provider']),
            models.Index(fields=['tax_id']),
            models.Index(fields=['category']),
        ]

    def __str__(self):
        display_name = self.name or self.tax_id
        roles = []
        if self.is_client:
            roles.append('Cliente')
        if self.is_provider:
            roles.append('Proveedor')
        role_str = f" ({', '.join(roles)})" if roles else ""
        return f"{display_name} ({self.tax_id}){role_str}"

    @property
    def role_display(self):
        """Retorna una descripción de los roles del contacto"""
        if self.is_client and self.is_provider:
            return "Cliente y Proveedor"
        elif self.is_client:
            return "Cliente"
        elif self.is_provider:
            return "Proveedor"
        else:
            return "Sin rol asignado"

    def clean(self):
        """Validación personalizada"""
        from django.core.exceptions import ValidationError
        if not self.is_client and not self.is_provider:
            raise ValidationError("El contacto debe tener al menos un rol: cliente o proveedor")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
