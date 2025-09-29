from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ContactViewSet

# Create a router and register our viewsets with it
router = DefaultRouter()
router.register(r'contacts', ContactViewSet, basename='contact')

app_name = 'contacts'

urlpatterns = [
    # Include all router URLs
    path('', include(router.urls)),
]

# Available endpoints will be:
# GET    /api/v1/contacts/                    # List all contacts
# POST   /api/v1/contacts/                    # Create new contact
# GET    /api/v1/contacts/{id}/               # Get specific contact
# PUT    /api/v1/contacts/{id}/               # Update contact (full)
# PATCH  /api/v1/contacts/{id}/               # Update contact (partial)
# DELETE /api/v1/contacts/{id}/               # Delete contact

# Custom actions:
# GET    /api/v1/contacts/stats/              # Get contact statistics
# GET    /api/v1/contacts/clients/            # Get only clients
# GET    /api/v1/contacts/providers/          # Get only providers
# GET    /api/v1/contacts/dual_role/          # Get dual-role contacts
# GET    /api/v1/contacts/search_by_rut/      # Search by RUT
# POST   /api/v1/contacts/{id}/toggle_client/ # Toggle client status
# POST   /api/v1/contacts/{id}/toggle_provider/ # Toggle provider status
# POST   /api/v1/contacts/{id}/toggle_active/  # Toggle active status