from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from django.conf import settings
from apps.chat.models import WebhookEvent, WhatsAppMessage


class Command(BaseCommand):
    help = 'Limpia datos antiguos de WhatsApp (webhooks, mensajes de prueba)'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=getattr(settings, 'WHATSAPP_CLEANUP_WEBHOOK_EVENTS_DAYS', 30),
            help='Días de antigüedad para eliminar eventos de webhooks',
        )
        parser.add_argument(
            '--test-days',
            type=int,
            default=getattr(settings, 'WHATSAPP_CLEANUP_TEST_EVENTS_DAYS', 7),
            help='Días de antigüedad para eliminar eventos de prueba',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Solo mostrar qué se eliminaría sin hacer cambios',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Mostrar información detallada',
        )
    
    def handle(self, *args, **options):
        days = options['days']
        test_days = options['test_days']
        dry_run = options['dry_run']
        verbose = options['verbose']
        
        if dry_run:
            self.stdout.write(self.style.WARNING("🔍 MODO DRY-RUN: Solo mostrando qué se eliminaría"))
        
        # Calcular fechas de corte
        webhook_cutoff = timezone.now() - timedelta(days=days)
        test_cutoff = timezone.now() - timedelta(days=test_days)
        
        self.stdout.write(f"📅 Eliminando eventos de webhooks anteriores a: {webhook_cutoff.strftime('%Y-%m-%d %H:%M:%S')}")
        self.stdout.write(f"🧪 Eliminando eventos de prueba anteriores a: {test_cutoff.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Limpiar eventos de prueba antiguos
        test_events_query = WebhookEvent.objects.filter(
            is_test=True,
            created_at__lt=test_cutoff
        )
        
        test_count = test_events_query.count()
        
        if verbose and test_count > 0:
            self.stdout.write(f"\n🧪 Eventos de prueba a eliminar:")
            for event in test_events_query[:10]:  # Mostrar solo los primeros 10
                self.stdout.write(f"  - {event.event_type} | {event.created_at} | {event.idempotency_key}")
            if test_count > 10:
                self.stdout.write(f"  ... y {test_count - 10} más")
        
        if not dry_run and test_count > 0:
            deleted_test = test_events_query.delete()
            self.stdout.write(self.style.SUCCESS(f"✅ {deleted_test[0]} eventos de prueba eliminados"))
        elif test_count > 0:
            self.stdout.write(f"📊 Se eliminarían {test_count} eventos de prueba")
        else:
            self.stdout.write("ℹ️ No hay eventos de prueba para eliminar")
        
        # Limpiar eventos procesados antiguos
        old_events_query = WebhookEvent.objects.filter(
            processing_status='processed',
            created_at__lt=webhook_cutoff,
            is_test=False
        )
        
        old_count = old_events_query.count()
        
        if verbose and old_count > 0:
            self.stdout.write(f"\n📜 Eventos antiguos procesados a eliminar:")
            for event in old_events_query[:10]:
                self.stdout.write(f"  - {event.event_type} | {event.created_at} | {event.processing_status}")
            if old_count > 10:
                self.stdout.write(f"  ... y {old_count - 10} más")
        
        if not dry_run and old_count > 0:
            deleted_old = old_events_query.delete()
            self.stdout.write(self.style.SUCCESS(f"✅ {deleted_old[0]} eventos antiguos eliminados"))
        elif old_count > 0:
            self.stdout.write(f"📊 Se eliminarían {old_count} eventos antiguos")
        else:
            self.stdout.write("ℹ️ No hay eventos antiguos para eliminar")
        
        # Limpiar eventos fallidos muy antiguos (90 días)
        failed_cutoff = timezone.now() - timedelta(days=90)
        failed_events_query = WebhookEvent.objects.filter(
            processing_status='failed',
            created_at__lt=failed_cutoff
        )
        
        failed_count = failed_events_query.count()
        
        if verbose and failed_count > 0:
            self.stdout.write(f"\n❌ Eventos fallidos muy antiguos a eliminar:")
            for event in failed_events_query[:5]:
                self.stdout.write(f"  - {event.event_type} | {event.created_at} | Error: {event.error_message[:50]}...")
            if failed_count > 5:
                self.stdout.write(f"  ... y {failed_count - 5} más")
        
        if not dry_run and failed_count > 0:
            deleted_failed = failed_events_query.delete()
            self.stdout.write(self.style.SUCCESS(f"✅ {deleted_failed[0]} eventos fallidos antiguos eliminados"))
        elif failed_count > 0:
            self.stdout.write(f"📊 Se eliminarían {failed_count} eventos fallidos antiguos")
        else:
            self.stdout.write("ℹ️ No hay eventos fallidos antiguos para eliminar")
        
        # Estadísticas finales
        total_events = WebhookEvent.objects.count()
        processed_events = WebhookEvent.objects.filter(processing_status='processed').count()
        failed_events = WebhookEvent.objects.filter(processing_status='failed').count()
        pending_events = WebhookEvent.objects.filter(processing_status='pending').count()
        
        self.stdout.write(f"\n📊 Estadísticas finales:")
        self.stdout.write(f"  • Total de eventos: {total_events}")
        self.stdout.write(f"  • Procesados: {processed_events}")
        self.stdout.write(f"  • Fallidos: {failed_events}")
        self.stdout.write(f"  • Pendientes: {pending_events}")
        
        if not dry_run:
            self.stdout.write(self.style.SUCCESS("\n🎉 Limpieza completada"))
        else:
            self.stdout.write(self.style.WARNING("\n🔍 Simulación completada. Usa --dry-run=false para ejecutar la limpieza"))