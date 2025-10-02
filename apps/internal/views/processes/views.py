"""
Vistas para gestión de procesos tributarios
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import JsonResponse

from apps.tasks.models import (
    ProcessTemplateConfig,
    ProcessTemplateTask,
    CompanySegment,
    ProcessAssignmentRule,
    Process
)
from apps.internal.forms.processes.forms import (
    ProcessTemplateConfigForm,
    ProcessTemplateTaskForm,
    CompanySegmentForm
)


@login_required
def processes_dashboard(request):
    """Dashboard principal de gestión de procesos"""

    # Estadísticas
    total_templates = ProcessTemplateConfig.objects.count()
    active_templates = ProcessTemplateConfig.objects.filter(status='active').count()
    total_segments = CompanySegment.objects.count()
    active_rules = ProcessAssignmentRule.objects.filter(is_active=True).count()

    # Templates recientes
    recent_templates = ProcessTemplateConfig.objects.order_by('-created_at')[:5]

    # Segmentos con conteo de empresas
    segments_with_counts = CompanySegment.objects.annotate(
        taxpayer_count=Count('taxpayers')
    ).order_by('-taxpayer_count')[:5]

    # Reglas activas
    active_assignment_rules = ProcessAssignmentRule.objects.filter(
        is_active=True
    ).select_related('template', 'segment').order_by('-priority')[:5]

    context = {
        'total_templates': total_templates,
        'active_templates': active_templates,
        'total_segments': total_segments,
        'active_rules': active_rules,
        'recent_templates': recent_templates,
        'segments_with_counts': segments_with_counts,
        'active_assignment_rules': active_assignment_rules,
    }

    return render(request, 'internal/processes/dashboard.html', context)


@login_required
def template_list(request):
    """Lista de plantillas de procesos"""

    status_filter = request.GET.get('status', '')
    process_type = request.GET.get('type', '')

    templates = ProcessTemplateConfig.objects.all()

    if status_filter:
        templates = templates.filter(status=status_filter)

    if process_type:
        templates = templates.filter(process_type=process_type)

    templates = templates.annotate(
        task_count=Count('template_tasks'),
        rule_count=Count('assignment_rules')
    ).order_by('-created_at')

    context = {
        'templates': templates,
        'status_filter': status_filter,
        'process_type': process_type,
        'process_types': Process.PROCESS_TYPES,
    }

    return render(request, 'internal/processes/templates/template_list.html', context)


@login_required
def template_detail(request, template_id):
    """Detalle de una plantilla de proceso"""

    template = get_object_or_404(ProcessTemplateConfig, id=template_id)
    tasks = template.template_tasks.all().order_by('execution_order')
    assignment_rules = template.assignment_rules.all()

    context = {
        'template': template,
        'tasks': tasks,
        'assignment_rules': assignment_rules,
    }

    return render(request, 'internal/processes/templates/template_detail.html', context)


@login_required
def template_create(request):
    """Crear una nueva plantilla de proceso"""

    if request.method == 'POST':
        form = ProcessTemplateConfigForm(request.POST)
        if form.is_valid():
            template = form.save()
            messages.success(request, f'Plantilla "{template.name}" creada exitosamente.')
            return redirect('internal:processes:template_detail', template_id=template.id)
    else:
        form = ProcessTemplateConfigForm()

    context = {
        'form': form,
        'action': 'Crear',
    }

    return render(request, 'internal/processes/templates/template_form.html', context)


@login_required
def template_edit(request, template_id):
    """Editar una plantilla de proceso"""

    template = get_object_or_404(ProcessTemplateConfig, id=template_id)

    if request.method == 'POST':
        form = ProcessTemplateConfigForm(request.POST, instance=template)
        if form.is_valid():
            template = form.save()
            messages.success(request, f'Plantilla "{template.name}" actualizada exitosamente.')
            return redirect('internal:processes:template_detail', template_id=template.id)
    else:
        form = ProcessTemplateConfigForm(instance=template)

    context = {
        'form': form,
        'template': template,
        'action': 'Editar',
    }

    return render(request, 'internal/processes/templates/template_form.html', context)


@login_required
def task_create(request, template_id):
    """Crear una nueva tarea para una plantilla"""

    template = get_object_or_404(ProcessTemplateConfig, id=template_id)

    if request.method == 'POST':
        form = ProcessTemplateTaskForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.template = template
            task.save()
            messages.success(request, f'Tarea "{task.task_title}" creada exitosamente.')
            return redirect('internal:processes:template_detail', template_id=template.id)
    else:
        # Pre-llenar con valores por defecto
        initial = {
            'template': template,
            'execution_order': template.template_tasks.count() + 1,
            'priority': 'medium',
            'task_type': 'manual',
        }
        form = ProcessTemplateTaskForm(initial=initial)

    context = {
        'form': form,
        'template': template,
        'action': 'Crear',
    }

    return render(request, 'internal/processes/templates/task_form.html', context)


@login_required
def task_edit(request, template_id, task_id):
    """Editar una tarea de una plantilla"""

    template = get_object_or_404(ProcessTemplateConfig, id=template_id)
    task = get_object_or_404(ProcessTemplateTask, id=task_id, template=template)

    if request.method == 'POST':
        form = ProcessTemplateTaskForm(request.POST, instance=task)
        if form.is_valid():
            task = form.save()
            messages.success(request, f'Tarea "{task.task_title}" actualizada exitosamente.')
            return redirect('internal:processes:template_detail', template_id=template.id)
    else:
        form = ProcessTemplateTaskForm(instance=task)

    context = {
        'form': form,
        'template': template,
        'task': task,
        'action': 'Editar',
    }

    return render(request, 'internal/processes/templates/task_form.html', context)


@login_required
def task_delete(request, template_id, task_id):
    """Eliminar una tarea de una plantilla"""

    template = get_object_or_404(ProcessTemplateConfig, id=template_id)
    task = get_object_or_404(ProcessTemplateTask, id=task_id, template=template)

    if request.method == 'POST':
        task_title = task.task_title
        task.delete()
        messages.success(request, f'Tarea "{task_title}" eliminada exitosamente.')
        return redirect('internal:processes:template_detail', template_id=template.id)

    context = {
        'template': template,
        'task': task,
    }

    return render(request, 'internal/processes/templates/task_confirm_delete.html', context)


@login_required
def segment_list(request):
    """Lista de segmentos de empresas"""

    segments = CompanySegment.objects.annotate(
        taxpayer_count=Count('taxpayers'),
        rule_count=Count('assignment_rules')
    ).order_by('name')

    context = {
        'segments': segments,
    }

    return render(request, 'internal/processes/segments/segment_list.html', context)


@login_required
def segment_detail(request, segment_id):
    """Detalle de un segmento"""

    segment = get_object_or_404(CompanySegment, id=segment_id)
    taxpayers = segment.taxpayers.all()[:20]  # Primeros 20
    assignment_rules = segment.assignment_rules.filter(is_active=True)

    context = {
        'segment': segment,
        'taxpayers': taxpayers,
        'assignment_rules': assignment_rules,
        'taxpayer_count': segment.taxpayers.count(),
    }

    return render(request, 'internal/processes/segments/segment_detail.html', context)


@login_required
def segment_create(request):
    """Crear un nuevo segmento"""

    if request.method == 'POST':
        form = CompanySegmentForm(request.POST)
        if form.is_valid():
            segment = form.save()
            messages.success(request, f'Segmento "{segment.name}" creado exitosamente.')
            return redirect('internal:processes:segment_detail', segment_id=segment.id)
    else:
        form = CompanySegmentForm()

    context = {
        'form': form,
        'action': 'Crear',
    }

    return render(request, 'internal/processes/segments/segment_form.html', context)


@login_required
def segment_edit(request, segment_id):
    """Editar un segmento"""

    segment = get_object_or_404(CompanySegment, id=segment_id)

    if request.method == 'POST':
        form = CompanySegmentForm(request.POST, instance=segment)
        if form.is_valid():
            segment = form.save()
            messages.success(request, f'Segmento "{segment.name}" actualizado exitosamente.')
            return redirect('internal:processes:segment_detail', segment_id=segment.id)
    else:
        form = CompanySegmentForm(instance=segment)

    context = {
        'form': form,
        'segment': segment,
        'action': 'Editar',
    }

    return render(request, 'internal/processes/segments/segment_form.html', context)


@login_required
def rule_list(request):
    """Lista de reglas de asignación"""

    is_active = request.GET.get('active', '')

    rules = ProcessAssignmentRule.objects.select_related(
        'template', 'segment'
    )

    if is_active == 'true':
        rules = rules.filter(is_active=True)
    elif is_active == 'false':
        rules = rules.filter(is_active=False)

    rules = rules.order_by('-priority', 'template__name')

    context = {
        'rules': rules,
        'is_active_filter': is_active,
    }

    return render(request, 'internal/processes/rules/rule_list.html', context)


@login_required
def rule_detail(request, rule_id):
    """Detalle de una regla de asignación"""

    rule = get_object_or_404(
        ProcessAssignmentRule.objects.select_related('template', 'segment'),
        id=rule_id
    )

    context = {
        'rule': rule,
    }

    return render(request, 'internal/processes/rules/rule_detail.html', context)


@login_required
def toggle_template_status(request, template_id):
    """Toggle del estado de una plantilla (active/inactive)"""

    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    template = get_object_or_404(ProcessTemplateConfig, id=template_id)

    if template.status == 'active':
        template.status = 'inactive'
        message = f'Plantilla "{template.name}" desactivada'
    else:
        template.status = 'active'
        message = f'Plantilla "{template.name}" activada'

    template.save()

    return JsonResponse({
        'success': True,
        'message': message,
        'new_status': template.status
    })


@login_required
def toggle_rule_status(request, rule_id):
    """Toggle del estado de una regla de asignación"""

    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    rule = get_object_or_404(ProcessAssignmentRule, id=rule_id)

    rule.is_active = not rule.is_active
    rule.save()

    message = f'Regla {"activada" if rule.is_active else "desactivada"}'

    return JsonResponse({
        'success': True,
        'message': message,
        'is_active': rule.is_active
    })
