from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
import logging

from apps.documents.models import Document
from apps.contacts.models import Contact

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Document)
def create_or_update_contacts_from_document(sender, instance, created, **kwargs):
    """
    Signal que se ejecuta cuando se guarda un documento.
    Crea o actualiza contactos para el emisor y receptor del documento.
    """
    if not instance.company:
        logger.warning(f"Document {instance.id} has no associated company, skipping contact creation")
        return

    # Usar transacción para asegurar consistencia
    with transaction.atomic():
        try:
            # Determinar roles basado en la dirección del documento
            if instance.is_issued_by_company:
                # El documento fue emitido por la empresa
                # El receptor es un cliente (compramos/vendimos a él)
                _create_or_update_contact_for_recipient(instance, is_client=True)

            elif instance.is_received_by_company:
                # El documento fue recibido por la empresa
                # El emisor es un proveedor (nos vendió)
                _create_or_update_contact_for_issuer(instance, is_provider=True)

            else:
                # Caso extraño donde el documento no coincide con la empresa
                logger.warning(
                    f"Document {instance.id} doesn't match company {instance.company.tax_id}. "
                    f"Issuer: {instance.issuer_full_rut}, Recipient: {instance.recipient_full_rut}"
                )

        except Exception as e:
            logger.error(f"Error creating contacts from document {instance.id}: {str(e)}")
            # Re-raise para que la transacción falle si hay errores críticos
            raise


def _create_or_update_contact_for_recipient(document, is_client=False, is_provider=False):
    """
    Crea o actualiza el contacto para el receptor del documento
    """
    tax_id = _format_rut(document.recipient_rut, document.recipient_dv)

    if not _is_valid_rut(tax_id):
        logger.warning(f"Invalid recipient RUT: {tax_id} in document {document.id}")
        return None

    contact, created = Contact.objects.get_or_create(
        company=document.company,
        tax_id=tax_id,
        defaults={
            'name': document.recipient_name,
            'address': document.recipient_address or '',
            'is_client': is_client,
            'is_provider': is_provider,
            'is_active': True,
        }
    )

    if not created:
        # Actualizar información si es necesario
        updated = False

        # Actualizar roles
        if is_client and not contact.is_client:
            contact.is_client = True
            updated = True

        if is_provider and not contact.is_provider:
            contact.is_provider = True
            updated = True

        # Actualizar información si está vacía
        if not contact.name and document.recipient_name:
            contact.name = document.recipient_name
            updated = True

        if not contact.address and document.recipient_address:
            contact.address = document.recipient_address
            updated = True

        if updated:
            contact.save()
            logger.info(f"Updated contact {contact.tax_id} from document {document.id}")
    else:
        logger.info(f"Created new contact {contact.tax_id} from document {document.id}")

    return contact


def _create_or_update_contact_for_issuer(document, is_client=False, is_provider=False):
    """
    Crea o actualiza el contacto para el emisor del documento
    """
    tax_id = _format_rut(document.issuer_company_rut, document.issuer_company_dv)

    if not _is_valid_rut(tax_id):
        logger.warning(f"Invalid issuer RUT: {tax_id} in document {document.id}")
        return None

    contact, created = Contact.objects.get_or_create(
        company=document.company,
        tax_id=tax_id,
        defaults={
            'name': document.issuer_name,
            'address': document.issuer_address or '',
            'category': document.issuer_activity or '',
            'is_client': is_client,
            'is_provider': is_provider,
            'is_active': True,
        }
    )

    if not created:
        # Actualizar información si es necesario
        updated = False

        # Actualizar roles
        if is_client and not contact.is_client:
            contact.is_client = True
            updated = True

        if is_provider and not contact.is_provider:
            contact.is_provider = True
            updated = True

        # Actualizar información si está vacía
        if not contact.name and document.issuer_name:
            contact.name = document.issuer_name
            updated = True

        if not contact.address and document.issuer_address:
            contact.address = document.issuer_address
            updated = True

        if not contact.category and document.issuer_activity:
            contact.category = document.issuer_activity
            updated = True

        if updated:
            contact.save()
            logger.info(f"Updated contact {contact.tax_id} from document {document.id}")
    else:
        logger.info(f"Created new contact {contact.tax_id} from document {document.id}")

    return contact


def _format_rut(rut, dv):
    """
    Formatea el RUT al formato estándar XX.XXX.XXX-X
    """
    try:
        # Limpiar y formatear RUT
        clean_rut = str(rut).strip().replace('.', '').replace('-', '')
        clean_dv = str(dv).strip().upper()

        # Formatear con puntos
        if len(clean_rut) >= 7:
            formatted = f"{clean_rut[:-6]}.{clean_rut[-6:-3]}.{clean_rut[-3:]}-{clean_dv}"
        else:
            formatted = f"{clean_rut}-{clean_dv}"

        return formatted
    except (ValueError, IndexError):
        return f"{rut}-{dv}"


def _is_valid_rut(tax_id):
    """
    Validación básica de formato de RUT chileno
    """
    if not tax_id:
        return False

    # Verificar formato básico
    parts = tax_id.split('-')
    if len(parts) != 2:
        return False

    rut_part = parts[0].replace('.', '')
    dv_part = parts[1].upper()

    # Verificar que la parte numérica sea válida
    if not rut_part.isdigit() or len(rut_part) < 7 or len(rut_part) > 8:
        return False

    # Verificar que el DV sea válido
    if len(dv_part) != 1 or dv_part not in '0123456789K':
        return False

    return True