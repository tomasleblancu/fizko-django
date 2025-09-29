from rest_framework import serializers
from .models import Contact


class ContactSerializer(serializers.ModelSerializer):
    """
    Serializer completo para Contact con información de roles
    """
    role_display = serializers.ReadOnlyField()

    class Meta:
        model = Contact
        fields = [
            'id',
            'company',
            'tax_id',
            'name',
            'email',
            'phone',
            'address',
            'category',
            'is_client',
            'is_provider',
            'is_active',
            'notes',
            'role_display',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'company', 'created_at', 'updated_at', 'role_display']

    def validate_tax_id(self, value):
        """Validate Chilean RUT format"""
        import re
        if not value:
            raise serializers.ValidationError("RUT es obligatorio")

        # Remove formatting for validation
        clean_value = value.replace('.', '').replace('-', '')
        if not re.match(r'^\d{7,8}[0-9Kk]$', clean_value):
            raise serializers.ValidationError("RUT debe tener formato válido (ej: 12.345.678-9)")

        # Ensure proper formatting
        rut_part = clean_value[:-1]
        dv_part = clean_value[-1].upper()

        if len(rut_part) >= 7:
            formatted = f"{rut_part[:-6]}.{rut_part[-6:-3]}.{rut_part[-3:]}-{dv_part}"
        else:
            formatted = f"{rut_part}-{dv_part}"

        return formatted

    def validate(self, data):
        """
        Validación personalizada - debe tener al menos un rol
        """
        is_client = data.get('is_client', False)
        is_provider = data.get('is_provider', False)

        if not is_client and not is_provider:
            raise serializers.ValidationError({
                'non_field_errors': ['El contacto debe tener al menos un rol: cliente o proveedor']
            })

        return data


class ContactCreateSerializer(serializers.ModelSerializer):
    """
    Serializer simplificado para crear contactos
    """
    class Meta:
        model = Contact
        fields = [
            'tax_id',
            'name',
            'email',
            'phone',
            'address',
            'category',
            'is_client',
            'is_provider',
            'notes',
        ]
        extra_kwargs = {
            'tax_id': {'required': True},
            'is_client': {'required': False, 'default': False},
            'is_provider': {'required': False, 'default': False},
        }

    def validate_tax_id(self, value):
        """Validate and format Chilean RUT"""
        import re
        if not value:
            raise serializers.ValidationError("RUT es obligatorio")

        # Remove formatting for validation
        clean_value = value.replace('.', '').replace('-', '')
        if not re.match(r'^\d{7,8}[0-9Kk]$', clean_value):
            raise serializers.ValidationError("RUT debe tener formato válido (ej: 12345678-9)")

        # Ensure proper formatting
        rut_part = clean_value[:-1]
        dv_part = clean_value[-1].upper()

        if len(rut_part) >= 7:
            formatted = f"{rut_part[:-6]}.{rut_part[-6:-3]}.{rut_part[-3:]}-{dv_part}"
        else:
            formatted = f"{rut_part}-{dv_part}"

        return formatted

    def validate(self, data):
        """
        Validación personalizada
        """
        is_client = data.get('is_client', False)
        is_provider = data.get('is_provider', False)

        # Si no se especifica ningún rol, por defecto es cliente
        if not is_client and not is_provider:
            data['is_client'] = True

        return data

    def create(self, validated_data):
        """
        Crear contacto asociado a la empresa del usuario actual
        """
        # La empresa se asigna en la vista basada en el usuario actual
        request = self.context.get('request')
        if request and hasattr(request.user, 'company'):
            validated_data['company'] = request.user.company

        return super().create(validated_data)


class ContactUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer para actualizar contactos (no permite cambiar tax_id ni company)
    """
    class Meta:
        model = Contact
        fields = [
            'name',
            'email',
            'phone',
            'address',
            'category',
            'is_client',
            'is_provider',
            'is_active',
            'notes',
        ]

    def validate(self, data):
        """
        Validación personalizada - debe mantener al menos un rol
        """
        # Obtener el objeto actual
        instance = getattr(self, 'instance', None)

        is_client = data.get('is_client', instance.is_client if instance else False)
        is_provider = data.get('is_provider', instance.is_provider if instance else False)

        if not is_client and not is_provider:
            raise serializers.ValidationError({
                'non_field_errors': ['El contacto debe tener al menos un rol: cliente o proveedor']
            })

        return data


class ContactListSerializer(serializers.ModelSerializer):
    """
    Serializer simplificado para listados de contactos
    """
    role_display = serializers.ReadOnlyField()

    class Meta:
        model = Contact
        fields = [
            'id',
            'tax_id',
            'name',
            'email',
            'phone',
            'category',
            'is_client',
            'is_provider',
            'is_active',
            'role_display',
            'created_at',
        ]


class ContactStatsSerializer(serializers.Serializer):
    """
    Serializer para estadísticas de contactos
    """
    total_contacts = serializers.IntegerField()
    total_clients = serializers.IntegerField()
    total_providers = serializers.IntegerField()
    dual_role_contacts = serializers.IntegerField()
    active_contacts = serializers.IntegerField()
    inactive_contacts = serializers.IntegerField()
    categories = serializers.DictField()