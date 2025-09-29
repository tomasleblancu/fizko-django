"""
URL configuration for chat templates (Django HTML views)
Separate from API URLs to avoid confusion
"""
from django.urls import path
from . import views

app_name = 'chat_admin'

urlpatterns = [
    # Agent Management
    path('agents/', views.agent_list, name='agent_list'),
    path('agents/create/', views.agent_create, name='agent_create'),
    path('agents/<int:agent_id>/', views.agent_detail, name='agent_detail'),
    path('agents/<int:agent_id>/edit/', views.agent_edit, name='agent_edit'),
    path('agents/<int:agent_id>/test/', views.test_agent, name='test_agent'),

    # Tool Management
    path('tools/', views.tools_library, name='tools_library'),
    path('tools/<str:tool_name>/', views.tool_detail, name='tool_detail'),
    path('agents/<int:agent_id>/tools/', views.agent_tools, name='agent_tools'),
    path('agents/<int:agent_id>/tools/assign/', views.assign_tool_to_agent, name='assign_tool_to_agent'),
    path('agents/<int:agent_id>/tools/<int:assignment_id>/remove/', views.remove_tool_from_agent, name='remove_tool_from_agent'),

    # Prompt Management
    path('agents/<int:agent_id>/prompts/create/', views.create_prompt, name='create_prompt'),
    path('agents/<int:agent_id>/prompts/<int:prompt_id>/delete/', views.delete_prompt_api, name='delete_prompt_api'),
    path('agents/<int:agent_id>/prompts/<int:prompt_id>/toggle/', views.toggle_prompt_api, name='toggle_prompt_api'),
    path('agents/<int:agent_id>/enhance-prompt/', views.enhance_prompt_api, name='enhance_prompt_api'),

    # Standalone prompt enhancement (for agent creation form)
    path('enhance-prompt/', views.enhance_prompt_standalone_api, name='enhance_prompt_standalone_api'),

    # Context Files Management
    path('agents/<int:agent_id>/context/', views.agent_context_files, name='agent_context_files'),

    # Dashboard
    path('', views.admin_dashboard, name='admin_dashboard'),
]