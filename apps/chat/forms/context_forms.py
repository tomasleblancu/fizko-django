"""
Formularios para gestión de archivos de contexto
"""
from django import forms
from django.core.validators import FileExtensionValidator
from apps.chat.models import ContextFile, AgentContextAssignment


class ContextFileUploadForm(forms.ModelForm):
    """
    Formulario para subir archivos de contexto
    """

    class Meta:
        model = ContextFile
        fields = ['name', 'description', 'file']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre descriptivo del archivo'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Descripción del contenido del archivo'
            }),
            'file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.json,.txt,.docx,.pdf'
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['file'].validators = [
            FileExtensionValidator(allowed_extensions=['json', 'txt', 'docx', 'pdf'])
        ]
        self.fields['name'].help_text = "Nombre que identificará este archivo"
        self.fields['description'].help_text = "Descripción opcional del contenido"
        self.fields['file'].help_text = "Archivos soportados: JSON, TXT, DOCX, PDF (máx. 50MB)"

    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file:
            # Validar tamaño (50MB máximo)
            max_size = 50 * 1024 * 1024  # 50MB
            if file.size > max_size:
                raise forms.ValidationError(
                    f"El archivo es demasiado grande ({file.size / 1024 / 1024:.1f}MB). "
                    f"El tamaño máximo permitido es 50MB."
                )

            # Validar extensión
            ext = file.name.split('.')[-1].lower()
            allowed_extensions = ['json', 'txt', 'docx', 'pdf']
            if ext not in allowed_extensions:
                raise forms.ValidationError(
                    f"Tipo de archivo no soportado. "
                    f"Extensiones permitidas: {', '.join(allowed_extensions)}"
                )

        return file


class AgentContextAssignmentForm(forms.ModelForm):
    """
    Formulario para asignar archivos de contexto a un agente
    """

    class Meta:
        model = AgentContextAssignment
        fields = ['priority', 'context_instructions', 'is_active']
        widgets = {
            'priority': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0,
                'max': 100,
                'value': 0
            }),
            'context_instructions': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Instrucciones específicas sobre cómo usar este archivo...'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['priority'].help_text = "Prioridad del archivo (0-100, mayor número = mayor prioridad)"
        self.fields['context_instructions'].help_text = "Instrucciones opcionales sobre cómo el agente debe usar este archivo"
        self.fields['is_active'].help_text = "Si este archivo está activo para el agente"


class ContextFileFilterForm(forms.Form):
    """
    Formulario para filtrar archivos de contexto
    """

    FILE_TYPE_CHOICES = [
        ('', 'Todos los tipos'),
        ('json', 'JSON'),
        ('txt', 'Texto'),
        ('docx', 'Word'),
        ('pdf', 'PDF'),
    ]

    STATUS_CHOICES = [
        ('', 'Todos los estados'),
        ('uploaded', 'Subido'),
        ('processing', 'Procesando'),
        ('processed', 'Procesado'),
        ('error', 'Error'),
    ]

    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Buscar por nombre o descripción...'
        })
    )

    file_type = forms.ChoiceField(
        choices=FILE_TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    agent = forms.ModelChoiceField(
        queryset=None,  # Se establecerá en la vista
        required=False,
        empty_label="Todos los agentes",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    def __init__(self, user=None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Filtrar agentes disponibles para el usuario
        if user:
            from apps.chat.models import AgentConfig
            from apps.chat.views import get_user_agents_query

            self.fields['agent'].queryset = AgentConfig.objects.filter(
                get_user_agents_query(user)
            ).order_by('name')


class ContextFileEditForm(forms.ModelForm):
    """
    Formulario para editar metadatos de archivo de contexto
    """

    class Meta:
        model = ContextFile
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['name'].help_text = "Nombre descriptivo del archivo"
        self.fields['description'].help_text = "Descripción del contenido del archivo"