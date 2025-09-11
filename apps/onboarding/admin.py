from django.contrib import admin
from .models import OnboardingStep, UserOnboarding

@admin.register(OnboardingStep)
class OnboardingStepAdmin(admin.ModelAdmin):
    list_display = ('step_order', 'title', 'is_required', 'is_active')
    list_filter = ('is_required', 'is_active')
    search_fields = ('name', 'title', 'description')
    ordering = ('step_order',)

@admin.register(UserOnboarding)
class UserOnboardingAdmin(admin.ModelAdmin):
    list_display = ('user_email', 'step', 'status', 'started_at', 'completed_at')
    list_filter = ('status', 'step')
    search_fields = ('user_email',)
