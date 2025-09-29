"""
Tareas de Celery para la aplicación documents
"""
import logging
from typing import Dict, Any, Optional
from celery import shared_task
from django.db import transaction
from django.db.models import Q

from .models import Document, DocumentType

logger = logging.getLogger(__name__)


@shared_task(bind=True, queue='default', autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def generate_document_references_task(self, company_id: Optional[int] = None, limit: Optional[int] = None):
    """
    Tarea para generar referencias automáticas entre documentos.

    Busca documentos con reference_folio no nulo y trata de encontrar el documento referenciado
    basándose en:
    - RUT emisor del documento de referencia
    - reference_folio -> folio del documento referenciado
    - reference_folio_type -> document_type del documento referenciado

    Args:
        company_id: ID de empresa específica para procesar (opcional)
        limit: Límite de documentos a procesar en esta ejecución (opcional)
    """
    task_id = self.request.id
    logger.info(f"🔗 [Task {task_id}] Iniciando generación de referencias de documentos")

    try:
        # Construir queryset base
        queryset = Document.objects.filter(
            reference_folio__isnull=False,
            reference_document__isnull=True  # Solo documentos sin referencia ya asignada
        ).exclude(reference_folio='')

        # Filtrar por empresa si se especifica
        if company_id:
            queryset = queryset.filter(company_id=company_id)
            logger.info(f"   Filtrando por empresa ID: {company_id}")

        # Aplicar límite si se especifica
        if limit:
            queryset = queryset[:limit]
            logger.info(f"   Limitando procesamiento a {limit} documentos")

        total_docs = queryset.count()
        logger.info(f"   Total documentos a procesar: {total_docs}")

        if total_docs == 0:
            logger.info("   No hay documentos para procesar")
            return {
                'status': 'success',
                'task_id': task_id,
                'processed': 0,
                'references_created': 0,
                'errors': 0,
                'message': 'No hay documentos para procesar'
            }

        processed = 0
        references_created = 0
        errors = 0

        # Procesar documentos en lotes para optimizar memoria
        batch_size = 100

        for offset in range(0, total_docs, batch_size):
            batch = queryset[offset:offset + batch_size]

            logger.info(f"   Procesando lote {offset//batch_size + 1}: {len(batch)} documentos")

            for document in batch:
                try:
                    with transaction.atomic():
                        result = _process_document_reference(document)

                        processed += 1
                        if result['reference_created']:
                            references_created += 1
                            logger.info(f"      ✅ Referencia creada: Doc {document.id} -> {result['referenced_document_id']}")

                except Exception as e:
                    errors += 1
                    logger.error(f"      ❌ Error procesando documento {document.id}: {str(e)}")

        logger.info(f"🎉 [Task {task_id}] Generación de referencias completada")
        logger.info(f"   Procesados: {processed}")
        logger.info(f"   Referencias creadas: {references_created}")
        logger.info(f"   Errores: {errors}")

        return {
            'status': 'success',
            'task_id': task_id,
            'processed': processed,
            'references_created': references_created,
            'errors': errors,
            'company_id': company_id
        }

    except Exception as e:
        logger.error(f"❌ [Task {task_id}] Error en generación de referencias: {str(e)}")
        raise


def _process_document_reference(document: Document) -> Dict[str, Any]:
    """
    Procesa un documento individual para encontrar su referencia.

    Args:
        document: Documento a procesar

    Returns:
        Dict con resultado del procesamiento
    """
    logger.debug(f"   🔍 Procesando documento ID {document.id} (Folio {document.folio})")

    # Validar que tenga los campos necesarios
    if not document.reference_folio:
        return {
            'reference_created': False,
            'reason': 'reference_folio vacío'
        }

    if not document.reference_folio_type:
        return {
            'reference_created': False,
            'reason': 'reference_folio_type vacío'
        }

    # Convertir reference_folio_type a código de DocumentType
    try:
        # Intentar convertir a entero (código directo)
        if document.reference_folio_type.isdigit():
            doc_type_code = int(document.reference_folio_type)
        else:
            # Si no es número, buscar por nombre
            doc_type = DocumentType.objects.filter(name__icontains=document.reference_folio_type).first()
            if not doc_type:
                return {
                    'reference_created': False,
                    'reason': f'DocumentType no encontrado para: {document.reference_folio_type}'
                }
            doc_type_code = doc_type.code

    except (ValueError, DocumentType.DoesNotExist):
        return {
            'reference_created': False,
            'reason': f'Error convirtiendo reference_folio_type: {document.reference_folio_type}'
        }

    # Buscar documento referenciado
    try:
        # Buscar por RUT emisor, tipo documento y folio
        referenced_doc = Document.objects.filter(
            issuer_company_rut=document.issuer_company_rut,
            issuer_company_dv=document.issuer_company_dv,
            document_type__code=doc_type_code,
            folio=int(document.reference_folio)
        ).first()

        if not referenced_doc:
            logger.debug(f"      No se encontró documento referenciado: RUT {document.issuer_company_rut}-{document.issuer_company_dv}, Tipo {doc_type_code}, Folio {document.reference_folio}")
            return {
                'reference_created': False,
                'reason': f'Documento referenciado no encontrado: RUT {document.issuer_company_rut}-{document.issuer_company_dv}, Tipo {doc_type_code}, Folio {document.reference_folio}'
            }

        # Crear la referencia
        document.reference_document = referenced_doc
        document.save(update_fields=['reference_document'])

        logger.debug(f"      ✅ Referencia creada: {document.id} -> {referenced_doc.id}")

        return {
            'reference_created': True,
            'referenced_document_id': referenced_doc.id,
            'referenced_folio': referenced_doc.folio,
            'referenced_type': referenced_doc.document_type.code
        }

    except ValueError:
        return {
            'reference_created': False,
            'reason': f'reference_folio no es un número válido: {document.reference_folio}'
        }
    except Exception as e:
        logger.error(f"      ❌ Error buscando documento referenciado: {str(e)}")
        return {
            'reference_created': False,
            'reason': f'Error en búsqueda: {str(e)}'
        }


@shared_task(bind=True, queue='default')
def generate_references_for_company_task(self, company_id: int, limit: Optional[int] = 500):
    """
    Genera referencias para documentos de una empresa específica.

    Args:
        company_id: ID de la empresa
        limit: Límite de documentos a procesar
    """
    return generate_document_references_task.apply_async(
        args=[company_id, limit],
        task_id=f"refs_company_{company_id}_{self.request.id}"
    ).get()


@shared_task(bind=True, queue='default')
def generate_references_batch_task(self, batch_size: int = 1000):
    """
    Procesa referencias en lotes para evitar timeouts en grandes volúmenes.

    Args:
        batch_size: Tamaño del lote a procesar
    """
    task_id = self.request.id
    logger.info(f"📦 [Task {task_id}] Procesando referencias en lotes de {batch_size}")

    return generate_document_references_task.apply_async(
        args=[None, batch_size],
        task_id=f"refs_batch_{batch_size}_{task_id}"
    ).get()