"""
Serializers para formularios tributarios
"""
from rest_framework import serializers
from .models import TaxForm, TaxFormTemplate, TaxFormField, TaxFormPayment
from apps.companies.serializers import CompanySerializer


class TaxFormTemplateSerializer(serializers.ModelSerializer):
    """
    Serializer para templates de formularios
    """
    class Meta:
        model = TaxFormTemplate
        fields = [
            'id', 'form_code', 'name', 'description', 'form_type',
            'version', 'is_active', 'form_structure', 'validation_rules',
            'calculation_rules', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class TaxFormFieldSerializer(serializers.ModelSerializer):
    """
    Serializer para campos de formularios
    """
    value = serializers.ReadOnlyField()

    class Meta:
        model = TaxFormField
        fields = [
            'id', 'field_code', 'field_name', 'field_type', 'section',
            'line_number', 'value', 'is_required', 'is_calculated',
            'calculation_formula', 'validation_rules'
        ]


class TaxFormPaymentSerializer(serializers.ModelSerializer):
    """
    Serializer para pagos de formularios
    """
    class Meta:
        model = TaxFormPayment
        fields = [
            'id', 'payment_method', 'amount', 'payment_date', 'status',
            'bank_code', 'transaction_id', 'authorization_code',
            'receipt_number', 'sii_payment_id', 'notes', 'created_at'
        ]
        read_only_fields = ['created_at']


class TaxFormSerializer(serializers.ModelSerializer):
    """
    Serializer para formularios tributarios
    """
    company = CompanySerializer(read_only=True)
    company_id = serializers.IntegerField(write_only=True, required=False)
    template = TaxFormTemplateSerializer(read_only=True)
    template_id = serializers.IntegerField(write_only=True)
    fields = TaxFormFieldSerializer(many=True, read_only=True)
    payments = TaxFormPaymentSerializer(many=True, read_only=True)
    is_overdue = serializers.ReadOnlyField()
    balance_due = serializers.ReadOnlyField()
    needs_detail_extraction = serializers.ReadOnlyField()
    has_recent_details = serializers.ReadOnlyField()

    class Meta:
        model = TaxForm
        fields = [
            'id', 'company', 'company_id', 'company_rut', 'company_dv',
            'template', 'template_id', 'tax_year', 'tax_month', 'tax_period',
            'status', 'due_date', 'submission_date', 'form_data', 'calculated_values',
            'validation_errors', 'total_tax_due', 'total_paid', 'balance_due',
            'sii_folio', 'sii_response', 'is_overdue', 'fields', 'payments',
            'details_extracted', 'details_extracted_at', 'details_extraction_method',
            'needs_detail_extraction', 'has_recent_details',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'balance_due']

    def validate(self, data):
        """
        Validaciones personalizadas
        """
        # Validar que tax_month sea válido si está presente
        tax_month = data.get('tax_month')
        if tax_month is not None and not (1 <= tax_month <= 12):
            raise serializers.ValidationError(
                {'tax_month': 'El mes debe estar entre 1 y 12'}
            )

        # Validar que total_paid no sea mayor que total_tax_due
        total_tax_due = data.get('total_tax_due')
        total_paid = data.get('total_paid', 0)

        if total_tax_due is not None and total_paid > total_tax_due:
            raise serializers.ValidationError(
                {'total_paid': 'El total pagado no puede ser mayor al total del impuesto'}
            )

        return data

    def create(self, validated_data):
        """
        Crear formulario y calcular balance
        """
        form = super().create(validated_data)
        form.calculate_balance()
        form.save()
        return form

    def update(self, instance, validated_data):
        """
        Actualizar formulario y recalcular balance
        """
        form = super().update(instance, validated_data)
        form.calculate_balance()
        form.save()
        return form


class TaxFormDetailsSerializer(serializers.ModelSerializer):
    """
    Serializer especializado para detalles extraídos de formularios F29
    """
    company_name = serializers.CharField(source='company.business_name', read_only=True)
    company_tax_id = serializers.CharField(source='company.tax_id', read_only=True)
    template_name = serializers.CharField(source='template.name', read_only=True)
    form_type = serializers.CharField(source='template.form_type', read_only=True)
    needs_detail_extraction = serializers.ReadOnlyField()
    has_recent_details = serializers.ReadOnlyField()

    class Meta:
        model = TaxForm
        fields = [
            'id', 'company_name', 'company_tax_id', 'sii_folio', 'tax_period',
            'template_name', 'form_type', 'status',
            'details_extracted', 'details_extracted_at', 'details_extraction_method',
            'details_data', 'needs_detail_extraction', 'has_recent_details',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class TaxFormListSerializer(serializers.ModelSerializer):
    """
    Serializer simplificado para listado de formularios
    """
    company_name = serializers.CharField(source='company.business_name', read_only=True)
    company_tax_id = serializers.CharField(source='company.tax_id', read_only=True)
    template_name = serializers.CharField(source='template.name', read_only=True)
    form_type = serializers.CharField(source='template.form_type', read_only=True)
    is_overdue = serializers.ReadOnlyField()
    details_extracted = serializers.ReadOnlyField()

    class Meta:
        model = TaxForm
        fields = [
            'id', 'company_name', 'company_tax_id', 'company_rut', 'company_dv',
            'template_name', 'form_type', 'tax_year', 'tax_month', 'tax_period',
            'status', 'due_date', 'total_tax_due', 'total_paid', 'balance_due',
            'sii_folio', 'is_overdue', 'details_extracted', 'created_at'
        ]