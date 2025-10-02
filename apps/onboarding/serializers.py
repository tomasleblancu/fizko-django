from rest_framework import serializers
from .models import OnboardingStep, UserOnboarding
# OnboardingProgress temporalmente deshabilitado


class OnboardingStepSerializer(serializers.ModelSerializer):
    """
    Serializer para pasos de onboarding
    """
    class Meta:
        model = OnboardingStep
        fields = [
            'id',
            'name',
            'title',
            'description',
            'step_order',
            'is_required',
            'step_config',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class UserOnboardingSerializer(serializers.ModelSerializer):
    """
    Serializer para el onboarding del usuario
    """
    step_title = serializers.CharField(source='step.title', read_only=True)
    step_order = serializers.IntegerField(source='step.step_order', read_only=True)
    step_name = serializers.CharField(source='step.name', read_only=True)
    
    class Meta:
        model = UserOnboarding
        fields = [
            'id',
            'user_email',
            'company_rut',
            'company_dv',
            'step',
            'step_title',
            'step_order',
            'step_name',
            'status',
            'started_at',
            'completed_at',
            'step_data',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


# class OnboardingProgressSerializer(serializers.ModelSerializer):
#     """
#     Serializer para el progreso de onboarding
#     DISABLED: OnboardingProgress modelo no existe
#     """
#     class Meta:
#         model = OnboardingProgress
#         fields = [
#             'user_email',
#             'total_steps',
#             'completed_steps',
#             'progress_percentage',
#             'is_completed',
#             'last_activity'
#         ]


class CompleteStepSerializer(serializers.Serializer):
    """
    Serializer para completar un paso de onboarding
    """
    step = serializers.IntegerField(help_text="Número del paso a completar")
    data = serializers.JSONField(required=False, help_text="Datos específicos del paso")
    status = serializers.ChoiceField(
        choices=['not_started', 'in_progress', 'completed', 'skipped'],
        default='completed'
    )


class OnboardingStatusSerializer(serializers.Serializer):
    """
    Serializer para el estado general del onboarding
    """
    user_id = serializers.IntegerField()
    is_completed = serializers.BooleanField()
    current_step = serializers.IntegerField()
    completed_steps = serializers.ListField(child=serializers.IntegerField())
    step_data = serializers.JSONField()
    total_steps = serializers.IntegerField()
    progress_percentage = serializers.FloatField()