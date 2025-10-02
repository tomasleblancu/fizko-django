"""
Formularios para gestión de configuración de agentes
"""
from django import forms
from django.contrib.auth.models import User
from apps.chat.models.agent_config import (
    AgentConfig,
    AgentPrompt,
    AgentTool,
    AgentModelConfig
)


class AgentConfigForm(forms.ModelForm):
    """Formulario para configuración básica de agentes"""

    class Meta:
        model = AgentConfig
        fields = [
            'name',
            'agent_type',
            'description',
            'status',
            'model_name',
            'temperature',
            'max_tokens',
            'system_prompt',
            'context_instructions'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre del agente'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Descripción del agente'
            }),
            'system_prompt': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 8,
                'placeholder': 'Instrucciones principales del agente...'
            }),
            'context_instructions': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Instrucciones de contexto específicas...'
            }),
            'temperature': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.1',
                'min': '0',
                'max': '2'
            }),
            'max_tokens': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'max': '8000'
            }),
            'model_name': forms.Select(attrs={'class': 'form-control'}),
            'agent_type': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'})
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Opciones de modelos disponibles
        model_choices = [
            ('gpt-4.1-nano', 'GPT-4.1 Nano'),
            ('gpt-4-turbo', 'GPT-4 Turbo'),
            ('gpt-4', 'GPT-4'),
            ('gpt-3.5-turbo', 'GPT-3.5 Turbo'),
        ]
        self.fields['model_name'].widget = forms.Select(
            choices=model_choices,
            attrs={'class': 'form-control'}
        )


class AgentPromptForm(forms.ModelForm):
    """Formulario para prompts de agentes"""

    class Meta:
        model = AgentPrompt
        fields = [
            'prompt_type',
            'name',
            'content',
            'variables',
            'is_active',
            'priority'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre del prompt'
            }),
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 10,
                'placeholder': 'Contenido del prompt...'
            }),
            'variables': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Lista de variables JSON: ["variable1", "variable2"]'
            }),
            'priority': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0'
            }),
            'prompt_type': forms.Select(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }

    def clean_variables(self):
        """Validar que variables sea una lista JSON válida"""
        variables = self.cleaned_data.get('variables')
        if variables:
            try:
                import json
                if isinstance(variables, str):
                    parsed = json.loads(variables)
                else:
                    parsed = variables

                if not isinstance(parsed, list):
                    raise forms.ValidationError("Variables debe ser una lista")

                return parsed
            except (json.JSONDecodeError, TypeError):
                raise forms.ValidationError("Variables debe ser una lista JSON válida")
        return []


class AgentToolForm(forms.ModelForm):
    """Formulario para herramientas de agentes"""

    class Meta:
        model = AgentTool
        fields = [
            'tool_name',
            'tool_function',
            'category',
            'description',
            'is_enabled',
            'parameters'
        ]
        widgets = {
            'tool_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre de la herramienta'
            }),
            'tool_function': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'apps.chat.services.tools.search_sii_faqs'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Descripción de la herramienta'
            }),
            'parameters': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Parámetros JSON: {"param1": "value1"}'
            }),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'is_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }

    def clean_parameters(self):
        """Validar que parameters sea un diccionario JSON válido"""
        parameters = self.cleaned_data.get('parameters')
        if parameters:
            try:
                import json
                if isinstance(parameters, str):
                    parsed = json.loads(parameters)
                else:
                    parsed = parameters

                if not isinstance(parsed, dict):
                    raise forms.ValidationError("Parámetros debe ser un diccionario")

                return parsed
            except (json.JSONDecodeError, TypeError):
                raise forms.ValidationError("Parámetros debe ser un diccionario JSON válido")
        return {}


class AgentModelConfigForm(forms.ModelForm):
    """Formulario para configuración avanzada del modelo"""

    class Meta:
        model = AgentModelConfig
        fields = [
            'top_p',
            'frequency_penalty',
            'presence_penalty',
            'stop_sequences',
            'timeout_seconds',
            'max_retries'
        ]
        widgets = {
            'top_p': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.1',
                'min': '0',
                'max': '1'
            }),
            'frequency_penalty': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.1',
                'min': '-2',
                'max': '2'
            }),
            'presence_penalty': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.1',
                'min': '-2',
                'max': '2'
            }),
            'stop_sequences': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Lista JSON: ["\\n", "END"]'
            }),
            'timeout_seconds': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'max': '300'
            }),
            'max_retries': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'max': '10'
            })
        }

    def clean_stop_sequences(self):
        """Validar que stop_sequences sea una lista JSON válida"""
        stop_sequences = self.cleaned_data.get('stop_sequences')
        if stop_sequences:
            try:
                import json
                if isinstance(stop_sequences, str):
                    parsed = json.loads(stop_sequences)
                else:
                    parsed = stop_sequences

                if not isinstance(parsed, list):
                    raise forms.ValidationError("Stop sequences debe ser una lista")

                return parsed
            except (json.JSONDecodeError, TypeError):
                raise forms.ValidationError("Stop sequences debe ser una lista JSON válida")
        return []


class BulkToolForm(forms.Form):
    """Formulario para activar/desactivar herramientas en lote"""

    ACTIONS = [
        ('enable', 'Habilitar'),
        ('disable', 'Deshabilitar'),
        ('delete', 'Eliminar'),
    ]

    tools = forms.ModelMultipleChoiceField(
        queryset=AgentTool.objects.none(),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        required=True
    )
    action = forms.ChoiceField(
        choices=ACTIONS,
        widget=forms.Select(attrs={'class': 'form-control'}),
        required=True
    )

    def __init__(self, agent_config, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tools'].queryset = AgentTool.objects.filter(
            agent_config=agent_config
        )


class TestAgentForm(forms.Form):
    """Formulario para probar agentes"""

    message = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Escribe tu mensaje de prueba aquí...'
        }),
        required=True,
        label="Mensaje de Prueba"
    )

    context_data = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 5,
            'placeholder': '{"user_name": "Juan", "company": "Empresa Test"}'
        }),
        required=False,
        label="Datos de Contexto (JSON)",
        help_text="Datos adicionales para el contexto del agente"
    )

    def clean_context_data(self):
        """Validar que context_data sea JSON válido"""
        context_data = self.cleaned_data.get('context_data')
        if context_data:
            try:
                import json
                return json.loads(context_data)
            except json.JSONDecodeError:
                raise forms.ValidationError("Datos de contexto debe ser JSON válido")
        return {}