from rest_framework import serializers
from .models import Company


class CompanyCreateSerializer(serializers.ModelSerializer):
    """Serializer para crear una nueva compañía (simplificado para nuevos modelos)"""
    
    class Meta:
        model = Company
        fields = [
            'tax_id', 'business_name', 'display_name', 'email', 'mobile_phone', 
            'website', 'electronic_biller', 'person_company', 'preferred_currency'
        ]
        extra_kwargs = {
            'tax_id': {'required': True},
            'business_name': {'required': True},
            'email': {'required': True}
        }

    def validate_tax_id(self, value):
        """Validate Chilean RUT format"""
        import re
        if not re.match(r'^\d{7,8}-[0-9Kk]$', value):
            raise serializers.ValidationError("RUT debe tener formato 12345678-9")
        return value


class CompanySerializer(serializers.ModelSerializer):
    """Serializer completo para Company con campos derivados del TaxPayer"""
    # Campos readonly derivados del TaxPayer
    full_rut = serializers.ReadOnlyField()
    name = serializers.ReadOnlyField()
    razon_social = serializers.ReadOnlyField()
    sii_address = serializers.ReadOnlyField()
    activity_description = serializers.ReadOnlyField()
    activity_start_date = serializers.ReadOnlyField()
    is_verified_with_sii = serializers.ReadOnlyField()
    
    class Meta:
        model = Company
        fields = '__all__'


class CompanyWithSiiDataSerializer(serializers.Serializer):
    """Serializer para crear compañía con datos del SII"""
    # Datos básicos de la compañía
    business_name = serializers.CharField(max_length=255, help_text="Nombre de fantasía")
    tax_id = serializers.CharField(max_length=12, help_text="RUT en formato 12345678-9")
    sii_password = serializers.CharField(max_length=200, help_text="Contraseña del SII")
    email = serializers.EmailField(required=False, allow_blank=True, help_text="Email de contacto (opcional)")
    mobile_phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    
    def validate_tax_id(self, value):
        """Validate Chilean RUT format"""
        import re
        if not re.match(r'^\d{7,8}-[0-9Kk]$', value):
            raise serializers.ValidationError("RUT debe tener formato 12345678-9")
        return value