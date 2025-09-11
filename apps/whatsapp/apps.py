from django.apps import AppConfig


class WhatsappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.whatsapp'
    verbose_name = 'WhatsApp Integration'
    
    def ready(self):
        import apps.whatsapp.signals  # noqa