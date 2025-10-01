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

    # Estadísticas de conversaciones
    from .models.conversation import Conversation, ConversationMessage
    total_conversations = Conversation.objects.filter(user=request.user).count()
    active_conversations = Conversation.objects.filter(user=request.user, status='active').count()
    total_messages = ConversationMessage.objects.filter(conversation__user=request.user).count()

    # Agentes recientes
    recent_agents = AgentConfig.objects.filter(
        get_user_agents_query(request.user)
    ).order_by('-created_at')[:5]

    context = {
        'total_agents': total_agents,
        'active_agents': active_agents,
        'total_tools': total_tools,
        'recent_agents': recent_agents,
        'categories': list(ToolCategory.objects.values_list('name', flat=True)),
        'total_conversations': total_conversations,
        'active_conversations': active_conversations,
        'total_messages': total_messages,
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


# ============================================================================
# VISTAS DE GESTIÓN DE CONVERSACIONES
# ============================================================================

@login_required
def conversation_list(request):
    """Lista de conversaciones del usuario"""
    from .models.conversation import Conversation

    # Obtener conversaciones del usuario autenticado
    conversations = Conversation.objects.filter(
        user=request.user
    ).order_by('-updated_at')

    # Filtrar por status si se proporciona
    status_filter = request.GET.get('status')
    if status_filter:
        conversations = conversations.filter(status=status_filter)

    # Calcular estadísticas
    total_conversations = Conversation.objects.filter(user=request.user).count()
    active_conversations = Conversation.objects.filter(user=request.user, status='active').count()
    archived_conversations = Conversation.objects.filter(user=request.user, status='archived').count()

    # Agregar información de mensaje count para cada conversación
    for conv in conversations:
        conv.message_count = conv.messages.count()
        conv.last_message = conv.messages.order_by('-created_at').first()

    # Paginación
    paginator = Paginator(conversations, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Determinar título de página según filtro
    if status_filter == 'active':
        page_title = 'Conversaciones Activas'
    elif status_filter == 'archived':
        page_title = 'Conversaciones Archivadas'
    else:
        page_title = 'Todas las Conversaciones'

    context = {
        'conversations': page_obj,
        'total_conversations': total_conversations,
        'active_conversations': active_conversations,
        'archived_conversations': archived_conversations,
        'current_filter': status_filter,
        'page_title': page_title,
    }

    return render(request, 'chat/conversations/conversation_list.html', context)


@login_required
def conversation_detail(request, conversation_id):
    """Detalle de una conversación específica"""
    from .models.conversation import Conversation, ConversationMessage

    # Obtener conversación asegurando que pertenece al usuario
    conversation = get_object_or_404(
        Conversation,
        id=conversation_id,
        user=request.user
    )

    # Obtener mensajes de la conversación
    messages = conversation.messages.order_by('created_at')

    # Paginación de mensajes (más recientes primero para la vista)
    paginator = Paginator(messages, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Calcular estadísticas de mensajes
    user_messages_count = messages.filter(role='user').count()
    assistant_messages_count = messages.filter(role='assistant').count()

    context = {
        'conversation': conversation,
        'messages': page_obj,
        'total_messages': messages.count(),
        'user_messages_count': user_messages_count,
        'assistant_messages_count': assistant_messages_count,
        'page_title': f'Conversación: {conversation.title or "Sin título"}',
    }

    return render(request, 'chat/conversations/conversation_detail.html', context)


@login_required
@require_http_methods(["POST"])
def add_assistant_message(request, conversation_id):
    """Agregar un mensaje como asistente a una conversación"""
    from .models.conversation import Conversation, ConversationMessage
    from django.utils import timezone
    import json

    try:
        # Obtener conversación asegurando que pertenece al usuario
        conversation = get_object_or_404(
            Conversation,
            id=conversation_id,
            user=request.user
        )

        # Obtener el contenido del mensaje
        if request.content_type == 'application/json':
            data = json.loads(request.body)
            message_content = data.get('content', '').strip()
        else:
            message_content = request.POST.get('content', '').strip()

        if not message_content:
            return JsonResponse({
                'success': False,
                'error': 'El contenido del mensaje no puede estar vacío'
            }, status=400)

        # Crear el nuevo mensaje como asistente
        message = ConversationMessage.objects.create(
            conversation=conversation,
            role='assistant',
            content=message_content,
            metadata={
                'added_by_admin': True,
                'admin_user_id': request.user.id,
                'timestamp': timezone.now().isoformat()
            }
        )

        # Actualizar la conversación
        conversation.updated_at = timezone.now()
        conversation.save()

        messages.success(request, f'Mensaje agregado exitosamente a la conversación')
        logger.info(f'Mensaje de asistente agregado a conversación {conversation_id} por usuario {request.user.id}')

        # Respuesta diferente según el tipo de request
        if request.content_type == 'application/json':
            return JsonResponse({
                'success': True,
                'message_id': str(message.id),
                'message': 'Mensaje agregado exitosamente'
            })
        else:
            return redirect('chat_admin:conversation_detail', conversation_id=conversation_id)

    except Exception as e:
        logger.error(f'Error agregando mensaje a conversación {conversation_id}: {e}')

        if request.content_type == 'application/json':
            return JsonResponse({
                'success': False,
                'error': 'Error interno del servidor'
            }, status=500)
        else:
            messages.error(request, 'Error al agregar el mensaje')
            return redirect('chat_admin:conversation_detail', conversation_id=conversation_id)


@login_required
@require_http_methods(["POST"])
def conversation_archive(request, conversation_id):
    """Archivar una conversación"""
    from .models.conversation import Conversation
    from django.utils import timezone

    try:
        # Obtener conversación asegurando que pertenece al usuario
        conversation = get_object_or_404(
            Conversation,
            id=conversation_id,
            user=request.user
        )

        # Archivar la conversación
        conversation.status = 'archived'
        conversation.ended_at = timezone.now()
        conversation.save()

        messages.success(request, f'Conversación "{conversation.title}" archivada exitosamente.')
        logger.info(f"Conversación {conversation_id} archivada por usuario {request.user.id}")

        return redirect('chat_admin:conversation_list')

    except Exception as e:
        logger.error(f"Error archivando conversación {conversation_id}: {e}")
        messages.error(request, 'Error al archivar la conversación.')
        return redirect('chat_admin:conversation_list')


@login_required
def conversation_analytics(request):
    """Vista de analytics y seguimiento completo de conversaciones"""
    from .models.conversation import Conversation, ConversationMessage
    from django.db.models import Count, Avg, Q
    from django.utils import timezone
    from datetime import datetime, timedelta
    import json

    # Estadísticas generales
    total_conversations = Conversation.objects.filter(user=request.user).count()
    active_conversations = Conversation.objects.filter(user=request.user, status='active').count()
    archived_conversations = Conversation.objects.filter(user=request.user, status='archived').count()
    total_messages = ConversationMessage.objects.filter(conversation__user=request.user).count()

    # Métricas de mensajes por rol
    user_messages = ConversationMessage.objects.filter(
        conversation__user=request.user, role='user'
    ).count()
    assistant_messages = ConversationMessage.objects.filter(
        conversation__user=request.user, role='assistant'
    ).count()

    # Conversaciones por fecha (últimos 30 días)
    last_30_days = timezone.now() - timedelta(days=30)
    daily_conversations = []
    for i in range(30):
        date = (timezone.now() - timedelta(days=i)).date()
        count = Conversation.objects.filter(
            user=request.user,
            created_at__date=date
        ).count()
        daily_conversations.append({
            'date': date.strftime('%Y-%m-%d'),
            'count': count
        })
    daily_conversations.reverse()

    # Distribución de longitud de conversaciones
    conversation_lengths = []
    conversations = Conversation.objects.filter(user=request.user).prefetch_related('messages')
    for conv in conversations:
        msg_count = conv.messages.count()
        conversation_lengths.append({
            'conversation_id': str(conv.id),
            'title': conv.title[:50] if conv.title else 'Sin título',
            'message_count': msg_count,
            'status': conv.status,
            'created_at': conv.created_at.strftime('%Y-%m-%d %H:%M')
        })

    # Estadísticas de agentes más utilizados
    agent_stats = {}
    for conv in conversations:
        agent = conv.agent_name or 'Sin especificar'
        if agent not in agent_stats:
            agent_stats[agent] = {'count': 0, 'total_messages': 0}
        agent_stats[agent]['count'] += 1
        agent_stats[agent]['total_messages'] += conv.messages.count()

    # Mensajes por hora del día
    hourly_messages = {}
    for hour in range(24):
        hourly_messages[hour] = ConversationMessage.objects.filter(
            conversation__user=request.user,
            created_at__hour=hour
        ).count()

    # Conversaciones más activas (por número de mensajes)
    most_active_conversations = list(conversations.annotate(
        msg_count=Count('messages')
    ).order_by('-msg_count')[:10])

    # Promedio de mensajes por conversación
    avg_messages_per_conversation = ConversationMessage.objects.filter(
        conversation__user=request.user
    ).count() / max(total_conversations, 1)

    context = {
        'analytics': {
            'total_conversations': total_conversations,
            'active_conversations': active_conversations,
            'archived_conversations': archived_conversations,
            'total_messages': total_messages,
            'user_messages': user_messages,
            'assistant_messages': assistant_messages,
            'avg_messages_per_conversation': round(avg_messages_per_conversation, 1),
        },
        'daily_conversations': daily_conversations,
        'conversation_lengths': conversation_lengths,
        'agent_stats': agent_stats,
        'hourly_messages': hourly_messages,
        'most_active_conversations': most_active_conversations,
        'page_title': 'Analytics de Conversaciones',
    }

    return render(request, 'chat/conversations/conversation_analytics.html', context)