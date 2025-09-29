"""
Vistas Django para gestión de configuración de agentes LangChain
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator
from django.db import transaction
import json
import logging

from .models.agent_config import (
    AgentConfig,
    AgentPrompt,
    AgentTool,
    AgentModelConfig,
    AgentVersion
)
from .forms import (
    AgentConfigForm,
    AgentPromptForm,
    AgentToolForm,
    AgentModelConfigForm,
    BulkToolForm,
    TestAgentForm
)

logger = logging.getLogger(__name__)


def get_user_agents_query(user):
    """Helper para obtener Q query que incluye agentes globales y de empresas del usuario"""
    from django.db.models import Q
    return Q(company__isnull=True) | Q(company__user_roles__user=user, company__user_roles__active=True)


# ============================================================================
# VISTAS PRINCIPALES DE GESTIÓN DE AGENTES
# ============================================================================

@login_required
def agent_list(request):
    """Lista de agentes configurados"""
    from django.db.models import Q

    # Incluir agentes globales (sin company) y agentes específicos de las empresas del usuario
    agents = AgentConfig.objects.filter(
        Q(company__isnull=True) |  # Agentes globales
        Q(company__user_roles__user=request.user, company__user_roles__active=True)  # Agentes de empresa
    ).select_related('company').order_by('agent_type', 'name')

    # Paginación
    paginator = Paginator(agents, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'agents': page_obj,
        'total_agents': agents.count()
    }
    return render(request, 'chat/agents/agent_list.html', context)


@login_required
def agent_detail(request, agent_id):
    """Detalle de un agente específico"""
    from django.db.models import Q

    agent = get_object_or_404(
        AgentConfig,
        Q(id=agent_id) & (
            Q(company__isnull=True) |  # Agentes globales
            Q(company__user_roles__user=request.user, company__user_roles__active=True)  # Agentes de empresa
        )
    )

    context = {
        'agent': agent,
        'prompts': agent.prompts.all().order_by('-priority', 'prompt_type'),
        'tools': agent.tool_assignments.all().order_by('common_tool__category', 'common_tool__display_name'),
        'versions': agent.versions.all()[:5]  # Últimas 5 versiones
    }
    return render(request, 'chat/agents/agent_detail.html', context)


@login_required
def agent_create(request):
    """Crear nuevo agente"""
    if request.method == 'POST':
        form = AgentConfigForm(request.POST)
        if form.is_valid():
            agent = form.save(commit=False)
            agent.created_by = request.user

            # Asignar empresa del usuario
            company = request.user.companies.filter(
                user_roles__active=True
            ).first()
            agent.company = company

            agent.save()

            # Crear configuración de modelo por defecto
            AgentModelConfig.objects.create(agent_config=agent)

            messages.success(request, f'Agente "{agent.name}" creado exitosamente.')
            return redirect('chat:agent_detail', agent_id=agent.id)
    else:
        form = AgentConfigForm()

    return render(request, 'chat/agents/agent_form.html', {
        'form': form,
        'title': 'Crear Nuevo Agente'
    })


@login_required
def agent_edit(request, agent_id):
    """Editar agente existente"""
    agent = get_object_or_404(
        AgentConfig,
        get_user_agents_query(request.user),
        id=agent_id
    )

    if request.method == 'POST':
        form = AgentConfigForm(request.POST, instance=agent)
        if form.is_valid():
            # Crear versión antes de guardar cambios
            version_number = f"v{agent.versions.count() + 1}"
            AgentVersion.objects.create(
                agent_config=agent,
                version_number=version_number,
                description=f"Actualización automática - {request.user.username}",
                config_snapshot=agent.get_full_config(),
                created_by=request.user
            )

            form.save()
            messages.success(request, f'Agente "{agent.name}" actualizado exitosamente.')
            return redirect('chat:agent_detail', agent_id=agent.id)
    else:
        form = AgentConfigForm(instance=agent)

    return render(request, 'chat/agents/agent_form.html', {
        'form': form,
        'agent': agent,
        'title': f'Editar {agent.name}'
    })


# ============================================================================
# GESTIÓN DE HERRAMIENTAS COMUNES
# ============================================================================

@login_required
def tools_library(request):
    """Biblioteca de herramientas disponibles"""
    from .models.common_tools import CommonTool, ToolCategory
    from django.db.models import Q

    # Obtener filtros
    category_filter = request.GET.get('category', '')
    search_query = request.GET.get('search', '')

    # Obtener herramientas desde la base de datos
    tools = CommonTool.objects.all().select_related('category')

    # Aplicar filtros
    if category_filter:
        tools = tools.filter(category__name=category_filter)

    if search_query:
        tools = tools.filter(
            Q(display_name__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(name__icontains=search_query)
        )

    # Organizar por categoría
    tools_by_category = {}
    for tool in tools:
        cat_name = tool.category.name if tool.category else 'Sin categoría'
        if cat_name not in tools_by_category:
            tools_by_category[cat_name] = {
                'name': cat_name,
                'tools': []
            }

        # Calcular parámetros opcionales y requeridos
        required_params = tool.required_parameters or []
        all_params = list((tool.parameters_schema or {}).keys())
        optional_params = [p for p in all_params if p not in required_params]

        # Convertir CommonTool a formato compatible con template
        tool_info = {
            'id': tool.id,
            'name': tool.name,
            'tool_name': tool.name,  # Para compatibilidad con template
            'display_name': tool.display_name,
            'description': tool.description,
            'function_path': tool.function_path,
            'category': cat_name,
            'required_parameters': required_params,
            'optional_parameters': optional_params,
            'parameters_schema': tool.parameters_schema or {}
        }
        tools_by_category[cat_name]['tools'].append(tool_info)

    # Obtener categorías disponibles
    categories = ToolCategory.objects.all().values_list('name', flat=True)

    context = {
        'tools_by_category': tools_by_category,
        'categories': list(categories),
        'current_category': category_filter,
        'search_query': search_query,
        'total_tools': CommonTool.objects.count()
    }
    return render(request, 'chat/tools/tools_library.html', context)


@login_required
def tool_detail(request, tool_name):
    """Detalle de una herramienta específica"""
    from .models.common_tools import AgentToolAssignment, CommonTool

    try:
        common_tool = CommonTool.objects.get(name=tool_name)

        # Obtener agentes que usan esta herramienta (incluyendo globales)
        from django.db.models import Q
        assignments = AgentToolAssignment.objects.filter(
            common_tool=common_tool,
            agent_config__in=AgentConfig.objects.filter(get_user_agents_query(request.user))
        ).select_related('agent_config', 'agent_config__company')

    except CommonTool.DoesNotExist:
        messages.error(request, f'Herramienta "{tool_name}" no encontrada.')
        return redirect('chat_admin:tools_library')

    context = {
        'tool': common_tool,
        'assigned_agents': assignments,
        'assigned_agents_count': assignments.count(),
        'can_test': True  # Podríamos agregar lógica de permisos
    }
    return render(request, 'chat/tools/tool_detail.html', context)


@login_required
def agent_tools(request, agent_id):
    """Gestión de herramientas de un agente"""
    from django.db.models import Q

    agent = get_object_or_404(
        AgentConfig,
        Q(id=agent_id) & (
            Q(company__isnull=True) |  # Agentes globales
            Q(company__user_roles__user=request.user, company__user_roles__active=True)  # Agentes de empresa
        )
    )

    from .models.common_tools import AgentToolAssignment, CommonTool, ToolCategory

    # Herramientas asignadas
    assigned_tools = AgentToolAssignment.objects.filter(
        agent_config=agent
    ).select_related('common_tool')

    # Herramientas disponibles (todas las que no están asignadas a este agente)
    assigned_tool_ids = [at.common_tool.id for at in assigned_tools]
    available_tools = CommonTool.objects.exclude(
        id__in=assigned_tool_ids
    ).select_related('category')

    # Convertir a formato compatible
    available_tools_list = []
    for tool in available_tools:
        # Calcular parámetros opcionales y requeridos
        required_params = tool.required_parameters or []
        all_params = list((tool.parameters_schema or {}).keys())
        optional_params = [p for p in all_params if p not in required_params]

        tool_info = {
            'id': tool.id,
            'name': tool.name,
            'tool_name': tool.name,  # Para compatibilidad con template
            'display_name': tool.display_name,
            'description': tool.description,
            'category': tool.category.name if tool.category else 'General',
            'required_parameters': required_params,
            'optional_parameters': optional_params,
            'parameters_schema': tool.parameters_schema or {}
        }
        available_tools_list.append(tool_info)

    context = {
        'agent': agent,
        'assigned_tools': assigned_tools,
        'available_tools': available_tools_list,
        'categories': list(ToolCategory.objects.values_list('name', flat=True))
    }
    return render(request, 'chat/agents/agent_tools.html', context)


@login_required
@require_http_methods(["POST"])
def assign_tool_to_agent(request, agent_id):
    """Asignar herramienta a un agente"""
    from django.db.models import Q

    agent = get_object_or_404(
        AgentConfig,
        Q(id=agent_id) & (
            Q(company__isnull=True) |  # Agentes globales
            Q(company__user_roles__user=request.user, company__user_roles__active=True)  # Agentes de empresa
        )
    )

    tool_id = request.POST.get('tool_id')
    if not tool_id:
        messages.error(request, 'ID de herramienta requerido.')
        return redirect('chat:agent_tools', agent_id=agent_id)

    from .models.common_tools import CommonTool, AgentToolAssignment

    # Verificar que la herramienta existe
    try:
        common_tool = CommonTool.objects.get(id=tool_id)
    except CommonTool.DoesNotExist:
        messages.error(request, f'Herramienta no encontrada.')
        return redirect('chat:agent_tools', agent_id=agent_id)

    # Crear asignación
    assignment, created = AgentToolAssignment.objects.get_or_create(
        agent_config=agent,
        common_tool=common_tool,
        defaults={
            'assigned_by': request.user,
            'is_enabled': True
        }
    )

    if created:
        messages.success(request, f'Herramienta "{common_tool.display_name}" asignada exitosamente.')
    else:
        messages.info(request, f'La herramienta "{common_tool.display_name}" ya está asignada.')

    return redirect('chat:agent_tools', agent_id=agent_id)


@login_required
@require_http_methods(["POST"])
def remove_tool_from_agent(request, agent_id, assignment_id):
    """Remover herramienta de un agente"""
    agent = get_object_or_404(
        AgentConfig,
        get_user_agents_query(request.user),
        id=agent_id
    )

    from .models.common_tools import AgentToolAssignment

    assignment = get_object_or_404(
        AgentToolAssignment,
        id=assignment_id,
        agent_config=agent
    )

    tool_name = assignment.common_tool.display_name
    assignment.delete()

    messages.success(request, f'Herramienta "{tool_name}" removida del agente.')
    return redirect('chat:agent_tools', agent_id=agent_id)


# ============================================================================
# TESTING Y CONFIGURACIÓN AVANZADA
# ============================================================================

@login_required
def test_agent(request, agent_id):
    """Interfaz para probar un agente"""
    agent = get_object_or_404(
        AgentConfig,
        get_user_agents_query(request.user),
        id=agent_id
    )

    if request.method == 'POST':
        form = TestAgentForm(request.POST)
        if form.is_valid():
            # Integrar con el sistema LangChain real
            import time
            import json
            from .agents import create_dynamic_agent

            message = form.cleaned_data['message']
            context_data = form.cleaned_data.get('context_data', {})

            # Parse context_data if it's a string
            if isinstance(context_data, str) and context_data.strip():
                try:
                    context_data = json.loads(context_data)
                except json.JSONDecodeError:
                    context_data = {}

            try:
                # Crear instancia del agente dinámico
                from langchain_core.messages import HumanMessage

                start_time = time.time()
                dynamic_agent = create_dynamic_agent(agent.id)

                # Preparar el estado del agente con el mensaje del usuario
                # Incluir el user_id del usuario actual para las herramientas que lo necesiten
                metadata = context_data or {}
                metadata['user_id'] = request.user.id

                agent_state = {
                    'messages': [HumanMessage(content=message)],
                    'metadata': metadata
                }

                response = dynamic_agent.run(agent_state)
                execution_time = time.time() - start_time

                # Extraer información de la respuesta
                if response and response.get('messages'):
                    agent_response = response['messages'][-1].content
                else:
                    agent_response = "No se pudo obtener respuesta del agente"

                # Obtener herramientas utilizadas desde las asignaciones activas
                tools_used = [
                    assignment.common_tool.display_name
                    for assignment in agent.tool_assignments.filter(is_enabled=True)
                ]

                test_result = {
                    'input_message': message,
                    'agent_response': agent_response,
                    'execution_time': f'{execution_time:.2f}s',
                    'tools_used': tools_used,
                    'context_applied': context_data
                }

            except Exception as e:
                logger.error(f"Error ejecutando agente {agent.id}: {e}")
                test_result = {
                    'input_message': message,
                    'agent_response': f'Error al ejecutar el agente: {str(e)}',
                    'execution_time': '0.0s',
                    'tools_used': [],
                    'context_applied': context_data
                }

            return render(request, 'chat/agents/test_result.html', {
                'agent': agent,
                'form': form,
                'result': test_result
            })
    else:
        form = TestAgentForm()

    context = {
        'agent': agent,
        'form': form,
        'available_tools': agent.tool_assignments.filter(is_enabled=True)
    }
    return render(request, 'chat/agents/test_agent.html', context)


# Vista eliminada - la funcionalidad de prompts ahora está integrada en agent_detail
# @login_required
# def agent_prompts(request, agent_id):
#     """Gestión de prompts de un agente"""
#     agent = get_object_or_404(
#         AgentConfig,
#         get_user_agents_query(request.user),
#         id=agent_id
#     )
#
#     prompts = agent.prompts.all().order_by('-priority', 'prompt_type')
#
#     context = {
#         'agent': agent,
#         'prompts': prompts
#     }
#     return render(request, 'chat/agents/agent_prompts.html', context)


@login_required
def create_prompt(request, agent_id):
    """Crear o editar prompt para un agente"""
    agent = get_object_or_404(
        AgentConfig,
        get_user_agents_query(request.user),
        id=agent_id
    )

    # Verificar si estamos editando un prompt existente
    edit_prompt_id = request.GET.get('edit')
    prompt_instance = None

    if edit_prompt_id:
        prompt_instance = get_object_or_404(
            AgentPrompt.objects.filter(agent_config=agent),
            id=edit_prompt_id
        )

    if request.method == 'POST':
        form = AgentPromptForm(request.POST, instance=prompt_instance)
        if form.is_valid():
            prompt = form.save(commit=False)
            prompt.agent_config = agent
            if not prompt_instance:  # Solo asignar created_by si es nuevo
                prompt.created_by = request.user
            prompt.save()

            if prompt_instance:
                messages.success(request, f'Prompt "{prompt.name}" actualizado exitosamente.')
            else:
                messages.success(request, f'Prompt "{prompt.name}" creado exitosamente.')
            return redirect('chat:agent_detail', agent_id=agent.id)
    else:
        form = AgentPromptForm(instance=prompt_instance)

    title = 'Editar Prompt' if prompt_instance else 'Crear Nuevo Prompt'

    return render(request, 'chat/prompts/prompt_form.html', {
        'form': form,
        'agent': agent,
        'title': title
    })


# ============================================================================
# VISTA PRINCIPAL DEL PANEL DE ADMINISTRACIÓN
# ============================================================================

@login_required
def admin_dashboard(request):
    """Panel principal de administración de agentes"""
    # Estadísticas generales
    total_agents = AgentConfig.objects.filter(
        get_user_agents_query(request.user)
    ).count()

    active_agents = AgentConfig.objects.filter(
        get_user_agents_query(request.user),
        status='active'
    ).count()

    from .models.common_tools import CommonTool, ToolCategory
    total_tools = CommonTool.objects.count()

    # Agentes recientes
    recent_agents = AgentConfig.objects.filter(
        get_user_agents_query(request.user)
    ).order_by('-created_at')[:5]

    context = {
        'total_agents': total_agents,
        'active_agents': active_agents,
        'total_tools': total_tools,
        'recent_agents': recent_agents,
        'categories': list(ToolCategory.objects.values_list('name', flat=True))
    }
    return render(request, 'chat/admin/dashboard.html', context)


# ============================================================================
# VISTAS TEMPORALES PARA ARCHIVOS DE CONTEXTO
# ============================================================================

@login_required
def agent_context_files(request, agent_id):
    """Vista para gestionar archivos de contexto de un agente"""
    from .models import AgentConfig, ContextFile, AgentContextAssignment

    # Obtener el agente
    agent = get_object_or_404(
        AgentConfig.objects.filter(get_user_agents_query(request.user)),
        id=agent_id
    )

    # Obtener archivos activos asignados al agente
    active_files = AgentContextAssignment.objects.filter(
        agent_config=agent,
        is_active=True
    ).select_related('context_file').order_by('-priority', '-created_at')

    # Obtener archivos disponibles para asignar (no asignados a este agente)
    assigned_file_ids = AgentContextAssignment.objects.filter(
        agent_config=agent
    ).values_list('context_file_id', flat=True)

    available_files = ContextFile.objects.filter(
        uploaded_by=request.user,
        status='processed'
    ).exclude(id__in=assigned_file_ids).order_by('-created_at')

    context = {
        'agent': agent,
        'active_files': active_files,
        'available_files': available_files,
    }
    return render(request, 'chat/agents/context_files.html', context)

@login_required
def upload_context_file(request, agent_id):
    """Vista temporal para subir archivos"""
    return JsonResponse({'message': 'Vista en desarrollo'})

@login_required
def assign_context_file(request, agent_id, file_id):
    """Vista temporal para asignar archivos"""
    return JsonResponse({'message': 'Vista en desarrollo'})

@login_required
def remove_context_file(request, agent_id, file_id):
    """Vista temporal para remover archivos"""
    return JsonResponse({'message': 'Vista en desarrollo'})

@login_required
def toggle_context_file(request, agent_id, file_id):
    """Vista temporal para activar/desactivar archivos"""
    return JsonResponse({'message': 'Vista en desarrollo'})

@login_required
def context_files_list(request):
    """Vista temporal para lista de archivos"""
    return JsonResponse({'message': 'Vista en desarrollo'})

@login_required
def context_file_detail(request, file_id):
    """Vista temporal para detalles de archivo"""
    return JsonResponse({'message': 'Vista en desarrollo'})

@login_required
def reprocess_context_file(request, file_id):
    """Vista temporal para reprocesar archivo"""
    return JsonResponse({'message': 'Vista en desarrollo'})


# ============================================================================
# API PARA PERFECCIONAMIENTO DE PROMPTS
# ============================================================================

@login_required
@require_http_methods(["POST"])
@csrf_exempt
def enhance_prompt_api(request, agent_id):
    """API para perfeccionar prompts usando IA"""
    try:
        import json
        from .services.prompt_enhancer import enhance_prompt_content
        from .models import AgentConfig

        # Verificar que el agente pertenezca al usuario
        agent = get_object_or_404(
            AgentConfig.objects.filter(get_user_agents_query(request.user)),
            id=agent_id
        )

        # Obtener datos del request
        data = json.loads(request.body)
        content = data.get('content', '').strip()
        prompt_type = data.get('prompt_type', 'system')

        if not content:
            return JsonResponse({
                'success': False,
                'error': 'El contenido del prompt no puede estar vacío'
            }, status=400)

        # Preparar contexto para el perfeccionamiento
        context = {
            'agent_name': agent.name,
            'agent_description': agent.description,
            'agent_type': agent.agent_type,
        }

        # Perfeccionar el prompt
        result = enhance_prompt_content(
            content=content,
            prompt_type=prompt_type,
            agent_type=agent.agent_type,
            context=context
        )

        if result['success']:
            logger.info(f"Prompt perfeccionado para agente {agent.name} (tipo: {prompt_type})")

        return JsonResponse(result)

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Formato JSON inválido'
        }, status=400)
    except Exception as e:
        logger.error(f"Error perfeccionando prompt: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Error interno del servidor'
        }, status=500)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def enhance_prompt_standalone_api(request):
    """API para perfeccionar prompts usando IA (standalone para formulario de creación)"""
    try:
        import json
        from .services.prompt_enhancer import enhance_prompt_content

        # Obtener datos del request
        data = json.loads(request.body)
        content = data.get('content', '').strip()
        prompt_type = data.get('prompt_type', 'system_prompt')
        agent_type = data.get('agent_type', 'general')
        context = data.get('context', {})

        if not content:
            return JsonResponse({
                'success': False,
                'error': 'El contenido del prompt no puede estar vacío'
            }, status=400)

        if not agent_type:
            return JsonResponse({
                'success': False,
                'error': 'El tipo de agente es requerido'
            }, status=400)

        # Perfeccionar el prompt
        result = enhance_prompt_content(
            content=content,
            prompt_type=prompt_type,
            agent_type=agent_type,
            context=context
        )

        if result['success']:
            logger.info(f"Prompt perfeccionado standalone (tipo: {prompt_type}, agente: {agent_type})")

        return JsonResponse(result)

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Formato JSON inválido'
        }, status=400)
    except Exception as e:
        logger.error(f"Error perfeccionando prompt standalone: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Error interno del servidor'
        }, status=500)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def delete_prompt_api(request, agent_id, prompt_id):
    """API para eliminar prompts"""
    try:
        from .models import AgentConfig, AgentPrompt

        # Verificar que el agente pertenezca al usuario
        agent = get_object_or_404(
            AgentConfig.objects.filter(get_user_agents_query(request.user)),
            id=agent_id
        )

        # Verificar que el prompt pertenezca al agente
        prompt = get_object_or_404(
            AgentPrompt.objects.filter(agent_config=agent),
            id=prompt_id
        )

        prompt_name = prompt.name
        prompt.delete()

        logger.info(f"Prompt '{prompt_name}' eliminado del agente {agent.name}")

        return JsonResponse({
            'success': True,
            'message': f'Prompt "{prompt_name}" eliminado exitosamente'
        })

    except Exception as e:
        logger.error(f"Error eliminando prompt: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Error interno del servidor'
        }, status=500)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def toggle_prompt_api(request, agent_id, prompt_id):
    """API para activar/desactivar prompts"""
    try:
        import json
        from .models import AgentConfig, AgentPrompt

        # Verificar que el agente pertenezca al usuario
        agent = get_object_or_404(
            AgentConfig.objects.filter(get_user_agents_query(request.user)),
            id=agent_id
        )

        # Verificar que el prompt pertenezca al agente
        prompt = get_object_or_404(
            AgentPrompt.objects.filter(agent_config=agent),
            id=prompt_id
        )

        # Obtener nuevo estado
        data = json.loads(request.body)
        new_status = data.get('is_active', not prompt.is_active)

        prompt.is_active = new_status
        prompt.save()

        action = "activado" if new_status else "desactivado"
        logger.info(f"Prompt '{prompt.name}' {action} en agente {agent.name}")

        return JsonResponse({
            'success': True,
            'message': f'Prompt "{prompt.name}" {action} exitosamente',
            'is_active': new_status
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Formato JSON inválido'
        }, status=400)
    except Exception as e:
        logger.error(f"Error cambiando estado de prompt: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Error interno del servidor'
        }, status=500)