from rest_framework import serializers
from .models import Document


class DocumentSerializer(serializers.ModelSerializer):
    """Serializer para documentos"""
    
    # Campos computados
    document_type_name = serializers.CharField(source='document_type.name', read_only=True)
    total_amount_formatted = serializers.SerializerMethodField()
    issuer_full_rut = serializers.ReadOnlyField()
    recipient_full_rut = serializers.ReadOnlyField()
    
    class Meta:
        model = Document
        fields = [
            'id', 'issuer_company_rut', 'issuer_company_dv', 'issuer_full_rut',
            'issuer_name', 'issuer_address', 'issuer_activity',
            'recipient_rut', 'recipient_dv', 'recipient_full_rut',
            'recipient_name', 'recipient_address',
            'document_type', 'document_type_name', 'folio', 'issue_date',
            'net_amount', 'tax_amount', 'exempt_amount', 'total_amount', 'total_amount_formatted',
            'status', 'sii_track_id', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'issuer_full_rut', 'recipient_full_rut']
    
    def get_total_amount_formatted(self, obj):
        """Formatear monto total en pesos chilenos"""
        if obj.total_amount:
            return f"${obj.total_amount:,.0f}".replace(',', '.')
        return "$0"


class DocumentCreateSerializer(serializers.ModelSerializer):
    """Serializer simplificado para crear documentos"""
    
    class Meta:
        model = Document
        fields = [
            'issuer_company_rut', 'issuer_company_dv', 'issuer_name', 'issuer_address',
            'recipient_rut', 'recipient_dv', 'recipient_name', 'recipient_address',
            'document_type', 'folio', 'issue_date',
            'net_amount', 'tax_amount', 'exempt_amount', 'total_amount'
        ]
    
    def validate(self, data):
        """Validaciones personalizadas"""
        # Verificar que el total sea la suma de neto + impuestos
        net = data.get('net_amount', 0)
        tax = data.get('tax_amount', 0)
        total = data.get('total_amount', 0)
        
        if abs((net + tax) - total) > 0.01:  # Permitir diferencias menores por redondeo
            raise serializers.ValidationError(
                "El monto total debe ser igual a la suma del monto neto más los impuestos"
            )
        
        return data


class FinancialSummarySerializer(serializers.Serializer):
    """Serializer para resúmenes financieros"""
    
    ventas = serializers.DictField(child=serializers.DecimalField(max_digits=15, decimal_places=2))
    compras = serializers.DictField(child=serializers.DecimalField(max_digits=15, decimal_places=2))
    periodo = serializers.DictField(child=serializers.DateField())