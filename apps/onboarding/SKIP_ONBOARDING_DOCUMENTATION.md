# Skip Onboarding for Invited Users

This document explains how the skip_onboarding functionality works for users who are invited to join existing companies.

## Overview

When users are invited to join a team, they should skip the standard onboarding process since:
1. They're joining an existing company (not creating a new one)
2. The onboarding flow is designed for company creators, not team members
3. They should have immediate access to the platform with their assigned role

## Implementation

### Database Schema

The `UserProfile` model includes a `skip_onboarding` boolean field:

```python
class UserProfile(TimeStampedModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    # ... other fields ...
    skip_onboarding = models.BooleanField(default=False)  # Para usuarios invitados
```

### Registration Flow for Invited Users

1. **User clicks invitation link** with a token (e.g., `/accept-invitation/{token}`)
2. **User registers** providing their details + the invitation token
3. **During registration**, the system:
   - Validates the invitation token
   - Sets `_invitation` attribute on the user object
   - Creates `UserProfile` with `skip_onboarding = True`
   - Accepts the invitation and creates `UserRole`

### API Endpoint: `/onboarding/user/needs_onboarding/`

The endpoint checks if a user needs to complete onboarding:

#### For Invited Users (skip_onboarding = True):
```json
{
    "needs_onboarding": false,
    "reason": "invited_user",
    "skip_onboarding": true,
    "required_steps": 0,
    "completed_required_steps": 0,
    "missing_steps": [],
    "is_finalized": false
}
```

#### For Regular Users (skip_onboarding = False):
```json
{
    "needs_onboarding": true,
    "reason": "finalization_check",
    "skip_onboarding": false,
    "required_steps": 8,
    "completed_required_steps": 0,
    "missing_steps": [
        {
            "step_order": 1,
            "name": "personal",
            "title": "Personal Information",
            "current_status": "not_started"
        }
        // ... more steps
    ],
    "is_finalized": false
}
```

#### For Users Who Completed Onboarding:
```json
{
    "needs_onboarding": false,
    "reason": "finalization_check",
    "skip_onboarding": false,
    "required_steps": 8,
    "completed_required_steps": 8,
    "missing_steps": [],
    "is_finalized": true
}
```

## Frontend Integration

The frontend should check the `needs_onboarding` endpoint after login:

```typescript
// In DjangoApp.tsx or similar
const checkOnboardingStatus = async () => {
  const response = await fetch('/api/v1/onboarding/user/needs_onboarding/');
  const data = await response.json();

  if (data.needs_onboarding) {
    // Redirect to onboarding flow
    navigate('/onboarding');
  } else {
    // Skip to dashboard
    navigate('/dashboard');
  }
};
```

## Testing

The implementation includes comprehensive tests covering:
- Regular users needing onboarding
- Invited users skipping onboarding
- Users who completed onboarding
- Users without profiles (auto-creation)
- Full invitation flow integration

Run tests with:
```bash
docker-compose exec django python manage.py test apps.onboarding.tests
```

## Edge Cases Handled

1. **User without profile**: Automatically creates one with `skip_onboarding = False`
2. **Invalid invitation tokens**: Handled in the registration serializer
3. **Expired invitations**: Cannot be accepted
4. **Multiple invitations**: Unique constraint prevents duplicates

## Key Files Modified

- `/apps/onboarding/views.py`: Updated `needs_onboarding` action
- `/apps/accounts/views.py`: Sets `skip_onboarding` during registration with invitation
- `/apps/accounts/serializers.py`: Handles invitation token validation
- `/apps/accounts/models.py`: UserProfile with `skip_onboarding` field
- `/apps/onboarding/tests.py`: Comprehensive test suite

## Database Migration

The `skip_onboarding` field was added in migration:
`/apps/accounts/migrations/0006_userprofile_onboarding_completed_and_more.py`

## Summary

This implementation ensures that:
✅ Invited users automatically skip onboarding
✅ Regular users go through normal onboarding
✅ The API clearly indicates why onboarding is/isn't needed
✅ Frontend can make routing decisions based on API response
✅ Edge cases are properly handled
✅ Comprehensive test coverage exists