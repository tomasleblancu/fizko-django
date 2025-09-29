from django.apps import AppConfig


class ContactsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.contacts"

    def ready(self):
        """
        Importar signals cuando la app esté lista
        """
        import apps.contacts.signals  # noqa
