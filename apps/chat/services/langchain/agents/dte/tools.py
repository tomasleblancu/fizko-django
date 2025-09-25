"""
Herramientas especializadas para DTE (Documentos Tributarios Electrónicos)
"""
from typing import Dict, List, Optional, Any
from langchain_core.tools import tool
from django.db.models import Q, Sum, Count
from django.utils import timezone
from datetime import datetime, timedelta
import logging

from apps.documents.models import Document, DocumentType
from apps.companies.models import Company

logger = logging.getLogger(__name__)


@tool
def get_document_types_info(category: Optional[str] = None) -> Dict[str, Any]:
    """
    Obtiene información sobre los tipos de documentos DTE disponibles.

    Args:
        category: Categoría opcional (invoice, receipt, credit_note, debit_note, dispatch, export, other)

    Returns:
        Dict con información de tipos de documentos
    """
    try:
        queryset = DocumentType.objects.filter(is_active=True)

        if category:
            queryset = queryset.filter(category=category)

        types = []
        for doc_type in queryset:
            types.append({
                'code': doc_type.code,
                'name': doc_type.name,
                'category': doc_type.category,
                'is_dte': doc_type.is_dte,
                'description': doc_type.description
            })

        return {
            'success': True,
            'document_types': types,
            'total': len(types)
        }
    except Exception as e:
        logger.error(f"Error getting document types: {e}")
        return {
            'success': False,
            'error': str(e),
            'document_types': []
        }


@tool
def validate_dte_code(dte_code: int) -> Dict[str, Any]:
    """
    Valida un código de DTE y retorna información sobre el tipo de documento.

    Args:
        dte_code: Código numérico del DTE (ej: 33, 34, 39, 61, etc.)

    Returns:
        Dict con validación y información del DTE
    """
    try:
        doc_type = DocumentType.objects.filter(code=dte_code, is_active=True).first()

        if doc_type:
            return {
                'valid': True,
                'code': doc_type.code,
                'name': doc_type.name,
                'category': doc_type.category,
                'is_dte': doc_type.is_dte,
                'requires_recipient': doc_type.requires_recipient,
                'description': doc_type.description
            }
        else:
            return {
                'valid': False,
                'message': f'Código DTE {dte_code} no encontrado o no está activo'
            }
    except Exception as e:
        logger.error(f"Error validating DTE code {dte_code}: {e}")
        return {
            'valid': False,
            'error': str(e)
        }


def _get_user_companies(user_id: Optional[int] = None) -> List[int]:
    """
    Helper para obtener las empresas asociadas al usuario actual.

    Args:
        user_id: ID del usuario autenticado

    Returns:
        Lista de IDs de empresas a las que el usuario tiene acceso
    """
    try:
        if not user_id:
            return []

        from apps.accounts.models import UserRole

        # Obtener las empresas donde el usuario tiene roles
        user_roles = UserRole.objects.filter(user_id=user_id).select_related('company')
        company_ids = []

        for role in user_roles:
            if role.company:
                company_ids.append(role.company.id)

        return company_ids
    except Exception as e:
        logger.error(f"Error getting user companies: {e}")
        return []


@tool
def search_documents_by_criteria(
    company_rut: Optional[str] = None,
    document_type_code: Optional[int] = None,
    status: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 10,
    user_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Busca documentos según criterios específicos, restringido a las empresas del usuario.

    Args:
        company_rut: RUT de la empresa (sin puntos ni guión)
        document_type_code: Código del tipo de documento
        status: Estado del documento (draft, pending, signed, sent, accepted, rejected, cancelled, processed)
        date_from: Fecha desde (formato YYYY-MM-DD)
        date_to: Fecha hasta (formato YYYY-MM-DD)
        limit: Límite de resultados (default: 10)
        user_id: ID del usuario autenticado (para restricción de acceso)

    Returns:
        Dict con documentos encontrados
    """
    try:
        # Obtener empresas del usuario - REQUERIDO para acceso
        if not user_id:
            return {
                'success': False,
                'error': 'Debe estar autenticado para acceder a los documentos',
                'documents': []
            }

        user_companies = _get_user_companies(user_id)
        if not user_companies:
            return {
                'success': False,
                'error': 'No tienes acceso a ninguna empresa',
                'documents': []
            }

        # RESTRICCIÓN DE SEGURIDAD: Filtrar solo por empresas del usuario usando FK
        queryset = Document.objects.filter(company_id__in=user_companies)

        # Filtrar por empresa específica (si se proporciona por RUT)
        if company_rut:
            clean_rut = company_rut.replace('.', '').replace('-', '')
            # Verificar acceso por RUT usando issuer_company_rut
            queryset = queryset.filter(
                Q(issuer_company_rut=clean_rut) | Q(recipient_rut=clean_rut)
            )

        # Filtrar por tipo de documento
        if document_type_code:
            queryset = queryset.filter(document_type__code=document_type_code)

        # Filtrar por estado
        if status:
            queryset = queryset.filter(status=status)

        # Filtrar por fechas
        if date_from:
            try:
                from_date = datetime.strptime(date_from, '%Y-%m-%d').date()
                queryset = queryset.filter(issue_date__gte=from_date)
            except ValueError:
                return {
                    'success': False,
                    'error': f'Formato de fecha incorrecto: {date_from}. Use YYYY-MM-DD'
                }

        if date_to:
            try:
                to_date = datetime.strptime(date_to, '%Y-%m-%d').date()
                queryset = queryset.filter(issue_date__lte=to_date)
            except ValueError:
                return {
                    'success': False,
                    'error': f'Formato de fecha incorrecto: {date_to}. Use YYYY-MM-DD'
                }

        # Limitar resultados
        documents = queryset.order_by('-issue_date')[:limit]

        results = []
        for doc in documents:
            results.append({
                'id': doc.id,
                'folio': doc.folio,
                'document_type': {
                    'code': doc.document_type.code,
                    'name': doc.document_type.name
                },
                'issuer_name': doc.issuer_name,
                'recipient_name': doc.recipient_name,
                'issue_date': doc.issue_date.strftime('%Y-%m-%d'),
                'status': doc.status,
                'total_amount': float(doc.total_amount),
                'net_amount': float(doc.net_amount),
                'tax_amount': float(doc.tax_amount)
            })

        return {
            'success': True,
            'documents': results,
            'total_found': queryset.count(),
            'showing': len(results)
        }
    except Exception as e:
        logger.error(f"Error searching documents: {e}")
        return {
            'success': False,
            'error': str(e),
            'documents': []
        }


@tool
def get_document_stats_summary(
    company_rut: Optional[str] = None,
    user_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Obtiene un resumen estadístico de documentos, restringido a las empresas del usuario.

    Args:
        company_rut: RUT de la empresa (opcional, sin puntos ni guión)
        user_id: ID del usuario autenticado (para restricción de acceso)

    Returns:
        Dict con estadísticas de documentos
    """
    try:
        # Obtener empresas del usuario - REQUERIDO para acceso
        if not user_id:
            return {
                'success': False,
                'error': 'Debe estar autenticado para consultar estadísticas',
                'stats': {}
            }

        user_companies = _get_user_companies(user_id)
        if not user_companies:
            return {
                'success': False,
                'error': 'No tienes acceso a ninguna empresa',
                'stats': {}
            }

        # RESTRICCIÓN DE SEGURIDAD: Filtrar solo por empresas del usuario usando FK
        queryset = Document.objects.filter(company_id__in=user_companies)

        # Filtrar por empresa específica (si se proporciona por RUT)
        if company_rut:
            clean_rut = company_rut.replace('.', '').replace('-', '')
            queryset = queryset.filter(
                Q(issuer_company_rut=clean_rut) | Q(recipient_rut=clean_rut)
            )

        # Estadísticas generales
        total_docs = queryset.count()

        # Por estado
        status_stats = {}
        for status_code, status_name in Document.STATUS_CHOICES:
            count = queryset.filter(status=status_code).count()
            status_stats[status_code] = {
                'name': status_name,
                'count': count
            }

        # Por tipo de documento
        type_stats = []
        for doc_type in DocumentType.objects.filter(is_active=True):
            count = queryset.filter(document_type=doc_type).count()
            if count > 0:
                type_stats.append({
                    'code': doc_type.code,
                    'name': doc_type.name,
                    'count': count
                })

        # Montos totales
        totals = queryset.aggregate(
            total_amount=Sum('total_amount'),
            net_amount=Sum('net_amount'),
            tax_amount=Sum('tax_amount')
        )

        return {
            'success': True,
            'stats': {
                'total_documents': total_docs,
                'by_status': status_stats,
                'by_type': type_stats,
                'amounts': {
                    'total_amount': float(totals['total_amount'] or 0),
                    'net_amount': float(totals['net_amount'] or 0),
                    'tax_amount': float(totals['tax_amount'] or 0)
                }
            }
        }
    except Exception as e:
        logger.error(f"Error getting document stats: {e}")
        return {
            'success': False,
            'error': str(e),
            'stats': {}
        }


@tool
def calculate_dte_tax_impact(
    net_amount: float,
    document_type_code: int,
    is_credit_note: bool = False
) -> Dict[str, Any]:
    """
    Calcula el impacto tributario de un DTE.

    Args:
        net_amount: Monto neto del documento
        document_type_code: Código del tipo de documento
        is_credit_note: True si es nota de crédito (afecta negativamente)

    Returns:
        Dict con cálculos tributarios
    """
    try:
        # Validar tipo de documento
        doc_type = DocumentType.objects.filter(code=document_type_code, is_active=True).first()
        if not doc_type:
            return {
                'success': False,
                'error': f'Código DTE {document_type_code} no encontrado'
            }

        # Tasa de IVA estándar en Chile
        iva_rate = 0.19

        # Calcular IVA según el tipo de documento
        iva_amount = 0
        exempt_amount = 0

        # Documentos afectos a IVA
        if document_type_code in [33, 39, 46, 52, 56, 110, 111]:  # Facturas, boletas, etc.
            iva_amount = net_amount * iva_rate
        # Documentos exentos
        elif document_type_code in [34, 41]:  # Facturas y boletas exentas
            exempt_amount = net_amount
        # Notas de crédito y débito
        elif document_type_code in [61, 56, 112]:
            if document_type_code == 61:  # Nota de crédito
                iva_amount = net_amount * iva_rate * (-1 if is_credit_note else 1)
            else:  # Nota de débito
                iva_amount = net_amount * iva_rate

        total_amount = net_amount + iva_amount + exempt_amount

        # Ajustar signos para notas de crédito
        if is_credit_note and document_type_code == 61:
            net_amount = -abs(net_amount)
            total_amount = -abs(total_amount)

        return {
            'success': True,
            'document_info': {
                'type_code': doc_type.code,
                'type_name': doc_type.name,
                'category': doc_type.category
            },
            'calculations': {
                'net_amount': round(net_amount, 2),
                'iva_amount': round(iva_amount, 2),
                'exempt_amount': round(exempt_amount, 2),
                'total_amount': round(total_amount, 2),
                'iva_rate_used': iva_rate
            },
            'tax_impact': {
                'affects_iva': iva_amount != 0,
                'iva_credit_debit': 'credit' if iva_amount > 0 else 'debit' if iva_amount < 0 else 'none',
                'is_exempt': exempt_amount > 0
            }
        }
    except Exception as e:
        logger.error(f"Error calculating tax impact: {e}")
        return {
            'success': False,
            'error': str(e)
        }


@tool
def get_recent_documents_summary(
    days_back: int = 30,
    company_rut: Optional[str] = None,
    document_type: Optional[str] = None,
    limit: int = 20,
    user_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Obtiene un resumen de documentos recientes con detalles específicos, restringido a las empresas del usuario.

    Args:
        days_back: Días hacia atrás para buscar (default: 30)
        company_rut: RUT de la empresa (opcional, sin puntos ni guión)
        document_type: Tipo de documento: 'received' (recibidos), 'issued' (emitidos), 'all' (todos)
        limit: Límite de documentos a mostrar (default: 20)
        user_id: ID del usuario autenticado (para restricción de acceso)

    Returns:
        Dict con resumen detallado de documentos recientes
    """
    try:
        from datetime import datetime, timedelta

        # Obtener empresas del usuario - REQUERIDO para acceso
        if not user_id:
            return {
                'success': False,
                'error': 'Debe estar autenticado para consultar documentos recientes',
                'recent_documents': []
            }

        user_companies = _get_user_companies(user_id)
        if not user_companies:
            return {
                'success': False,
                'error': 'No tienes acceso a ninguna empresa',
                'recent_documents': []
            }

        # Calcular fecha desde
        date_from = (datetime.now() - timedelta(days=days_back)).date()

        queryset = Document.objects.filter(issue_date__gte=date_from)

        # RESTRICCIÓN DE SEGURIDAD: Filtrar solo por empresas del usuario
        if user_companies:
            company_filter = Q()
            for user_company_rut in user_companies:
                company_filter |= (
                    Q(issuer_company_rut=user_company_rut) | Q(recipient_rut=user_company_rut)
                )
            queryset = queryset.filter(company_filter)

        # Filtrar por empresa específica (si se proporciona)
        if company_rut:
            clean_rut = company_rut.replace('.', '').replace('-', '')
            # Verificar que el usuario tenga acceso a esta empresa
            if user_companies and clean_rut not in user_companies:
                return {
                    'success': False,
                    'error': 'No tienes acceso a los documentos de esta empresa',
                    'recent_documents': []
                }

            if document_type == 'received':
                queryset = queryset.filter(recipient_rut=clean_rut)
            elif document_type == 'issued':
                queryset = queryset.filter(issuer_company_rut=clean_rut)
            else:
                queryset = queryset.filter(
                    Q(issuer_company_rut=clean_rut) | Q(recipient_rut=clean_rut)
                )

        # Ordenar por fecha más reciente
        recent_docs = queryset.order_by('-issue_date', '-created_at')[:limit]

        # Detalles de documentos
        documents_detail = []
        for doc in recent_docs:
            documents_detail.append({
                'id': doc.id,
                'folio': doc.folio,
                'document_type': {
                    'code': doc.document_type.code,
                    'name': doc.document_type.name
                },
                'issuer': {
                    'rut': f"{doc.issuer_company_rut}-{doc.issuer_company_dv}",
                    'name': doc.issuer_name
                },
                'recipient': {
                    'rut': f"{doc.recipient_rut}-{doc.recipient_dv}",
                    'name': doc.recipient_name
                },
                'issue_date': doc.issue_date.strftime('%Y-%m-%d'),
                'status': doc.status,
                'amounts': {
                    'net': float(doc.net_amount),
                    'tax': float(doc.tax_amount),
                    'total': float(doc.total_amount)
                },
                'days_ago': (datetime.now().date() - doc.issue_date).days
            })

        # Estadísticas del período
        period_stats = queryset.aggregate(
            total_documents=Count('id'),
            total_amount=Sum('total_amount'),
            net_amount=Sum('net_amount'),
            tax_amount=Sum('tax_amount')
        )

        # Resumen por tipo
        type_summary = []
        for doc_type in DocumentType.objects.filter(is_active=True):
            count = queryset.filter(document_type=doc_type).count()
            if count > 0:
                type_total = queryset.filter(document_type=doc_type).aggregate(
                    total=Sum('total_amount')
                )['total'] or 0

                type_summary.append({
                    'code': doc_type.code,
                    'name': doc_type.name,
                    'count': count,
                    'total_amount': float(type_total)
                })

        # Resumen por estado
        status_summary = {}
        for status_code, status_name in Document.STATUS_CHOICES:
            count = queryset.filter(status=status_code).count()
            if count > 0:
                status_summary[status_code] = {
                    'name': status_name,
                    'count': count
                }

        return {
            'success': True,
            'period_info': {
                'days_back': days_back,
                'date_from': date_from.strftime('%Y-%m-%d'),
                'date_to': datetime.now().date().strftime('%Y-%m-%d')
            },
            'summary': {
                'total_documents': period_stats['total_documents'],
                'total_amount': float(period_stats['total_amount'] or 0),
                'net_amount': float(period_stats['net_amount'] or 0),
                'tax_amount': float(period_stats['tax_amount'] or 0)
            },
            'by_type': type_summary,
            'by_status': status_summary,
            'recent_documents': documents_detail,
            'showing': len(documents_detail)
        }

    except Exception as e:
        logger.error(f"Error getting recent documents: {e}")
        return {
            'success': False,
            'error': str(e),
            'recent_documents': []
        }


@tool
def get_taxpayer_information(
    user_id: Optional[int] = None,
    include_raw_data: bool = True,
    include_socios: bool = True,
    include_actividades: bool = True,
    include_representantes: bool = True,
    include_direcciones: bool = True,
    include_timbrajes: bool = True
) -> Dict[str, Any]:
    """
    Obtiene información completa del contribuyente (Taxpayer) incluyendo raw data del SII.

    Args:
        user_id: ID del usuario autenticado (para restricción de acceso)
        include_raw_data: Incluir datos raw completos del SII
        include_socios: Incluir información de socios
        include_actividades: Incluir actividades económicas
        include_representantes: Incluir representantes legales
        include_direcciones: Incluir direcciones registradas
        include_timbrajes: Incluir información de documentos timbrados

    Returns:
        Dict con información completa del taxpayer
    """
    try:
        # Verificar autenticación
        if not user_id:
            return {
                'success': False,
                'error': 'Debe estar autenticado para acceder a información del contribuyente',
                'taxpayer_info': {}
            }

        # Obtener empresas del usuario
        user_companies = _get_user_companies(user_id)
        if not user_companies:
            return {
                'success': False,
                'error': 'No tienes acceso a ninguna empresa',
                'taxpayer_info': {}
            }

        # Importar el modelo aquí para evitar import circular
        from apps.companies.models import Company

        # Obtener la empresa del usuario (usar la primera disponible)
        company = Company.objects.filter(id__in=user_companies).first()
        if not company:
            return {
                'success': False,
                'error': 'No se encontró empresa asociada',
                'taxpayer_info': {}
            }

        # Verificar si tiene taxpayer
        if not hasattr(company, 'taxpayer') or not company.taxpayer:
            return {
                'success': False,
                'error': 'La empresa no tiene información de contribuyente registrada',
                'taxpayer_info': {}
            }

        taxpayer = company.taxpayer

        # Información básica del taxpayer
        taxpayer_info = {
            'basic_info': {
                'rut': taxpayer.rut,
                'dv': taxpayer.dv,
                'tax_id': taxpayer.tax_id,
                'razon_social': taxpayer.razon_social,
                'data_source': taxpayer.data_source,
                'last_sii_sync': taxpayer.last_sii_sync.isoformat() if taxpayer.last_sii_sync else None,
                'is_active': taxpayer.is_active,
                'is_verified': taxpayer.is_verified,
                'created_at': taxpayer.created_at.isoformat(),
                'updated_at': taxpayer.updated_at.isoformat()
            },
            'settings': taxpayer.setting_procesos
        }

        # Agregar información específica del SII raw data si está disponible
        if include_raw_data and taxpayer.sii_raw_data:
            sii_data = taxpayer.sii_raw_data

            # Información del contribuyente
            if 'contribuyente' in sii_data:
                contrib = sii_data['contribuyente']
                taxpayer_info['contribuyente'] = {
                    'razon_social': contrib.get('razonSocial'),
                    'email': contrib.get('eMail'),
                    'telefono_movil': contrib.get('telefonoMovil'),
                    'tipo_contribuyente': contrib.get('tipoContribuyenteDescripcion'),
                    'subtipo_contribuyente': contrib.get('subtipoContribuyenteDescrip'),
                    'fecha_inicio_actividades': contrib.get('fechaInicioActividades'),
                    'fecha_constitucion': contrib.get('fechaConstitucion'),
                    'glosa_actividad': contrib.get('glosaActividad'),
                    'segmento': contrib.get('segmentoDescripcion'),
                    'capital_por_enterar': contrib.get('capitalPorEnterar'),
                    'unidad_operativa': contrib.get('unidadOperativaDescripcion')
                }

            # Socios
            if include_socios and 'socios' in sii_data:
                taxpayer_info['socios'] = []
                for socio in sii_data['socios']:
                    socio_info = {
                        'rut': f"{socio.get('rut')}-{socio.get('dv')}",
                        'nombre_completo': f"{socio.get('nombres', '')} {socio.get('apellidoPaterno', '')} {socio.get('apellidoMaterno', '')}".strip(),
                        'razon_social': socio.get('razonSocial'),
                        'participacion_capital': socio.get('participacionCapital'),
                        'participacion_utilidades': socio.get('participacionUtilidades'),
                        'fecha_incorporacion': socio.get('fechaIncorporacion'),
                        'vigente': socio.get('vigente') == 'S',
                        'aporte_enterado': socio.get('aporteEnterado'),
                        'aporte_por_enterar': socio.get('aportePorEnterar')
                    }
                    taxpayer_info['socios'].append(socio_info)

            # Actividades económicas
            if include_actividades and 'actEcos' in sii_data:
                taxpayer_info['actividades_economicas'] = []
                for actividad in sii_data['actEcos']:
                    act_info = {
                        'codigo': actividad.get('codigo'),
                        'descripcion': actividad.get('descripcion'),
                        'fecha_inicio': actividad.get('fechaInicio'),
                        'afecto_iva': actividad.get('afectoIva') == 'S',
                        'categoria_tributaria': actividad.get('categoriaTributaria')
                    }
                    taxpayer_info['actividades_economicas'].append(act_info)

            # Representantes
            if include_representantes and 'representantes' in sii_data:
                taxpayer_info['representantes'] = []
                for rep in sii_data['representantes']:
                    rep_info = {
                        'rut': f"{rep.get('rut')}-{rep.get('dv')}",
                        'nombre_completo': f"{rep.get('nombres', '')} {rep.get('apellidoPaterno', '')} {rep.get('apellidoMaterno', '')}".strip(),
                        'razon_social': rep.get('razonSocial'),
                        'fecha_inicio': rep.get('fechaInicio'),
                        'fecha_termino': rep.get('fechaTermino'),
                        'vigente': rep.get('vigente') == 'S'
                    }
                    taxpayer_info['representantes'].append(rep_info)

            # Direcciones
            if include_direcciones and 'direcciones' in sii_data:
                taxpayer_info['direcciones'] = []
                for dir in sii_data['direcciones']:
                    dir_info = {
                        'calle': dir.get('calle'),
                        'numero': dir.get('numero'),
                        'departamento': dir.get('departamento'),
                        'bloque': dir.get('bloque'),
                        'comuna': dir.get('comunaDescripcion'),
                        'region': dir.get('regionDescripcion'),
                        'tipo_domicilio': dir.get('tipoDomicilioDescripcion'),
                        'tipo_propiedad': dir.get('tipoPropiedadDescripcion'),
                        'propietario_rut': f"{dir.get('rutPropietario')}-{dir.get('dvPropietario')}" if dir.get('rutPropietario') else None
                    }
                    taxpayer_info['direcciones'].append(dir_info)

            # Timbrajes (documentos autorizados)
            if include_timbrajes and 'timbrajes' in sii_data:
                taxpayer_info['documentos_timbrados'] = []
                for timbraje in sii_data['timbrajes']:
                    timb_info = {
                        'codigo': timbraje.get('codigo'),
                        'descripcion': timbraje.get('descripcion'),
                        'numero_inicial': timbraje.get('numeroInicial'),
                        'numero_final': timbraje.get('numeroFinal'),
                        'fecha_legalizacion': timbraje.get('fechaLegalizacion')
                    }
                    taxpayer_info['documentos_timbrados'].append(timb_info)

            # Raw data completo si se solicita
            if include_raw_data:
                taxpayer_info['sii_raw_data'] = sii_data

        return {
            'success': True,
            'taxpayer_info': taxpayer_info
        }

    except Exception as e:
        logger.error(f"Error getting taxpayer information: {e}")
        return {
            'success': False,
            'error': str(e),
            'taxpayer_info': {}
        }