"""
Formularios para gestión de procesos tributarios
"""
import json
from django import forms
from apps.tasks.models import (
    ProcessTemplateConfig,
    ProcessTemplateTask,
    CompanySegment,
    ProcessAssignmentRule,
    Process
)


class ProcessTemplateConfigForm(forms.ModelForm):
    """Formulario para configuración de plantillas de procesos"""

    # Campos adicionales para configuración de recurrencia
    recurrence_day = forms.IntegerField(
        required=False,
        min_value=1,
        max_value=31,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '12'
        }),
        label='Día del Vencimiento',
        help_text='Día del mes para el vencimiento (1-31)'
    )

    # Campos adicionales para template_config
    auto_sync_documents = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Auto-sincronizar Documentos',
        help_text='Sincronizar automáticamente documentos del SII'
    )

    require_approval = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Requiere Aprobación',
        help_text='El proceso requiere aprobación antes de completarse'
    )

    auto_calculate_iva = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Auto-calcular IVA',
        help_text='Calcular automáticamente el IVA basado en documentos'
    )

    include_credits = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Incluir Créditos',
        help_text='Incluir créditos fiscales en el cálculo'
    )

    class Meta:
        model = ProcessTemplateConfig
        fields = [
            'name',
            'process_type',
            'status',
            'default_recurrence_type',
            'description',
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: F29 Mensual Completo'
            }),
            'process_type': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'default_recurrence_type': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Descripción de la plantilla...'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Si estamos editando, cargar valores desde JSON
        if self.instance and self.instance.pk:
            # Cargar configuración de recurrencia
            if self.instance.default_recurrence_config:
                self.fields['recurrence_day'].initial = self.instance.default_recurrence_config.get('day_of_month')

            # Cargar template_config
            if self.instance.template_config:
                self.fields['auto_sync_documents'].initial = self.instance.template_config.get('auto_sync_documents', False)
                self.fields['require_approval'].initial = self.instance.template_config.get('require_approval', False)

            # Cargar default_values
            if self.instance.default_values:
                self.fields['auto_calculate_iva'].initial = self.instance.default_values.get('auto_calculate_iva', False)
                self.fields['include_credits'].initial = self.instance.default_values.get('include_credits', False)

    def save(self, commit=True):
        instance = super().save(commit=False)

        # Construir default_recurrence_config desde campos del formulario
        recurrence_day = self.cleaned_data.get('recurrence_day')
        if recurrence_day:
            instance.default_recurrence_config = {
                'day_of_month': recurrence_day,
                'months': list(range(1, 13))  # Todos los meses por defecto
            }

        # Construir template_config
        process_type = self.cleaned_data.get('process_type')
        template_config = {}

        if process_type in ['tax_monthly', 'tax_quarterly']:
            template_config['form_type'] = 'f29' if process_type == 'tax_monthly' else 'f3323'
            template_config['auto_sync_documents'] = self.cleaned_data.get('auto_sync_documents', False)
            template_config['require_approval'] = self.cleaned_data.get('require_approval', False)

        instance.template_config = template_config

        # Construir default_values
        default_values = {}
        if process_type in ['tax_monthly', 'tax_quarterly']:
            default_values['auto_calculate_iva'] = self.cleaned_data.get('auto_calculate_iva', False)
            default_values['include_credits'] = self.cleaned_data.get('include_credits', False)

        instance.default_values = default_values

        # Construir available_variables según tipo de proceso
        if process_type in ['tax_monthly', 'tax_quarterly']:
            instance.available_variables = ['period', 'company_name', 'rut', 'tax_year', 'tax_month']
        else:
            instance.available_variables = ['company_name', 'rut', 'tax_year']

        # Asignar created_by si es nuevo
        if not instance.pk and not instance.created_by:
            instance.created_by = 'system@fizko.cl'

        if commit:
            instance.save()

        return instance


class ProcessTemplateTaskForm(forms.ModelForm):
    """Formulario para tareas de plantilla"""

    class Meta:
        model = ProcessTemplateTask
        fields = [
            'task_title',
            'task_description',
            'task_type',
            'execution_order',
            'due_date_offset_days',
            'is_optional',
            'priority',
            'estimated_hours',
            'depends_on',
            'can_run_parallel',
            'due_date_from_previous',
        ]
        widgets = {
            'task_title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre de la tarea'
            }),
            'task_description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Descripción de la tarea...'
            }),
            'task_type': forms.Select(attrs={'class': 'form-select'}),
            'execution_order': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1
            }),
            'due_date_offset_days': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Días desde el inicio del proceso'
            }),
            'is_optional': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'estimated_hours': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Horas estimadas',
                'step': '0.5'
            }),
            'depends_on': forms.SelectMultiple(attrs={
                'class': 'form-select',
                'size': '3'
            }),
            'can_run_parallel': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'due_date_from_previous': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Filtrar depends_on para mostrar solo tareas de la misma plantilla
        if self.instance and self.instance.template_id:
            self.fields['depends_on'].queryset = ProcessTemplateTask.objects.filter(
                template_id=self.instance.template_id
            ).exclude(id=self.instance.id)


class CompanySegmentForm(forms.ModelForm):
    """Formulario para segmentos de empresas"""

    class Meta:
        model = CompanySegment
        fields = [
            'name',
            'description',
            'criteria',
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: Retail Grande'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Descripción del segmento...'
            }),
            'criteria': forms.Textarea(attrs={
                'class': 'form-control font-monospace',
                'rows': 8,
                'placeholder': '{"industry": "retail", "size": "large"}'
            }),
        }


class ProcessAssignmentRuleForm(forms.ModelForm):
    """Formulario para reglas de asignación"""

    class Meta:
        model = ProcessAssignmentRule
        fields = [
            'template',
            'segment',
            'priority',
            'is_active',
            'conditions',
        ]
        widgets = {
            'template': forms.Select(attrs={'class': 'form-select'}),
            'segment': forms.Select(attrs={'class': 'form-select'}),
            'priority': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0,
                'max': 100
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'conditions': forms.Textarea(attrs={
                'class': 'form-control font-monospace',
                'rows': 6,
                'placeholder': '{"condition": "value"}'
            }),
        }
