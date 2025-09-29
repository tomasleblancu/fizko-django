"""
Comando Django para generar referencias de documentos
"""
from django.core.management.base import BaseCommand, CommandError
from apps.documents.tasks import generate_document_references_task


class Command(BaseCommand):
    help = 'Genera referencias automáticas entre documentos basándose en reference_folio'

    def add_arguments(self, parser):
        parser.add_argument(
            '--company-id',
            type=int,
            help='ID de empresa específica para procesar'
        )
        parser.add_argument(
            '--limit',
            type=int,
            help='Límite de documentos a procesar'
        )
        parser.add_argument(
            '--async',
            action='store_true',
            help='Ejecutar como tarea asíncrona de Celery'
        )

    def handle(self, *args, **options):
        company_id = options.get('company_id')
        limit = options.get('limit')
        run_async = options.get('async', False)

        self.stdout.write(
            self.style.SUCCESS(
                '🔗 Iniciando generación de referencias de documentos...'
            )
        )

        if company_id:
            self.stdout.write(f'   Empresa ID: {company_id}')
        if limit:
            self.stdout.write(f'   Límite: {limit} documentos')

        try:
            if run_async:
                # Ejecutar como tarea asíncrona
                task = generate_document_references_task.delay(company_id, limit)
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✅ Tarea iniciada con ID: {task.id}'
                    )
                )
                self.stdout.write('   Monitorea el progreso en Flower: http://localhost:5555')
            else:
                # Ejecutar sincrónicamente
                result = generate_document_references_task(company_id, limit)

                self.stdout.write(
                    self.style.SUCCESS('🎉 Generación completada:')
                )
                self.stdout.write(f'   Procesados: {result["processed"]}')
                self.stdout.write(f'   Referencias creadas: {result["references_created"]}')
                self.stdout.write(f'   Errores: {result["errors"]}')

        except Exception as e:
            raise CommandError(f'Error ejecutando comando: {str(e)}')