from rest_framework import serializers
from .models import TaxPayer, TaxpayerActivity, TaxpayerAddress, TaxpayerPartner, TaxpayerRepresentative, TaxpayerStamp, TaxpayerSiiCredentials


class TaxPayerSerializer(serializers.ModelSerializer):
    """Serializer para TaxPayer"""
    full_rut = serializers.ReadOnlyField()
    is_persona_juridica = serializers.ReadOnlyField()
    formatted_address = serializers.ReadOnlyField()
    
    class Meta:
        model = TaxPayer
        fields = '__all__'
        read_only_fields = (
            'rut', 'dv', 'razon_social', 'nombre', 'tipo_contribuyente', 'estado',
            'actividad_description', 'glosa_actividad', 'fecha_inicio_actividades',
            'direccion', 'comuna', 'region', 'email', 'mobile_phone',
            'data_source', 'last_sii_sync', 'sii_raw_data', 'is_verified'
        )


class TaxPayerCreateSerializer(serializers.ModelSerializer):
    """Serializer para crear TaxPayer (solo campos básicos)"""
    
    class Meta:
        model = TaxPayer
        fields = ['tax_id', 'rut', 'dv']
        extra_kwargs = {
            'tax_id': {'required': True}
        }

    def validate_tax_id(self, value):
        """Validate Chilean RUT format"""
        import re
        if not re.match(r'^\d{7,8}-[0-9Kk]$', value):
            raise serializers.ValidationError("RUT debe tener formato 12345678-9")
        return value


class TaxpayerActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = TaxpayerActivity
        fields = '__all__'


class TaxpayerAddressSerializer(serializers.ModelSerializer):
    full_address = serializers.ReadOnlyField()
    
    class Meta:
        model = TaxpayerAddress
        fields = '__all__'


class TaxpayerPartnerSerializer(serializers.ModelSerializer):
    full_company_rut = serializers.ReadOnlyField()
    full_partner_rut = serializers.ReadOnlyField()
    
    class Meta:
        model = TaxpayerPartner
        fields = '__all__'


class TaxpayerRepresentativeSerializer(serializers.ModelSerializer):
    full_company_rut = serializers.ReadOnlyField()
    full_representative_rut = serializers.ReadOnlyField()
    is_valid = serializers.ReadOnlyField()
    
    class Meta:
        model = TaxpayerRepresentative
        fields = '__all__'


class TaxpayerStampSerializer(serializers.ModelSerializer):
    full_company_rut = serializers.ReadOnlyField()
    is_valid = serializers.ReadOnlyField()
    days_until_expiry = serializers.ReadOnlyField()
    
    class Meta:
        model = TaxpayerStamp
        fields = '__all__'


class TaxpayerSiiCredentialsSerializer(serializers.ModelSerializer):
    """Serializer para TaxpayerSiiCredentials (sin exponer la contraseña)"""
    is_credentials_valid = serializers.ReadOnlyField()
    
    class Meta:
        model = TaxpayerSiiCredentials
        fields = [
            'id', 'company', 'user', 'tax_id', 'is_active', 
            'last_verified', 'verification_failures', 'is_credentials_valid',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['last_verified', 'verification_failures']