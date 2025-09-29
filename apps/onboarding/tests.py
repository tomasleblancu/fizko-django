from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from apps.accounts.models import UserProfile, Role, TeamInvitation
from apps.companies.models import Company
from .models import OnboardingStep, UserOnboarding
from unittest.mock import patch

User = get_user_model()


class OnboardingSkipTestCase(TestCase):
    """
    Test cases for skip_onboarding functionality for invited users
    """

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()

        # Create a test user for company owner
        self.owner_user = User.objects.create_user(
            email='owner@test.com',
            username='owner',
            password='testpass123',
            first_name='Owner',
            last_name='Test'
        )

        # Create UserProfile for owner
        self.owner_profile = UserProfile.objects.create(
            user=self.owner_user,
            skip_onboarding=False
        )

        # Create a mock company (we don't have full company setup in test)
        self.test_company = Company.objects.create(
            business_name='Test Company',
            tax_id='12345678-9',
            email='test@company.com'
        )

        # Create roles
        self.owner_role = Role.objects.create(
            name='owner',
            description='Company owner',
            permissions={'all': True}
        )

        self.user_role = Role.objects.create(
            name='user',
            description='Regular user',
            permissions={'view': True}
        )

        # Create some onboarding steps
        self.step1 = OnboardingStep.objects.create(
            name='personal',
            title='Personal Information',
            step_order=1,
            is_required=True,
            is_active=True
        )

        self.step2 = OnboardingStep.objects.create(
            name='company',
            title='Company Information',
            step_order=2,
            is_required=True,
            is_active=True
        )

    def test_regular_user_needs_onboarding(self):
        """Test that a regular user (not invited) needs onboarding"""
        # Create a regular user
        regular_user = User.objects.create_user(
            email='regular@test.com',
            username='regular',
            password='testpass123'
        )

        # Create profile without skip_onboarding
        UserProfile.objects.create(
            user=regular_user,
            skip_onboarding=False
        )

        self.client.force_authenticate(user=regular_user)

        url = reverse('onboarding:user-onboarding-needs-onboarding')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Regular user should need onboarding
        self.assertTrue(data['needs_onboarding'])
        self.assertFalse(data['skip_onboarding'])
        self.assertEqual(data['reason'], 'finalization_check')

    def test_invited_user_skips_onboarding(self):
        """Test that an invited user skips onboarding"""
        # Create an invited user
        invited_user = User.objects.create_user(
            email='invited@test.com',
            username='invited',
            password='testpass123'
        )

        # Create profile with skip_onboarding=True (simulating invitation flow)
        UserProfile.objects.create(
            user=invited_user,
            skip_onboarding=True
        )

        self.client.force_authenticate(user=invited_user)

        url = reverse('onboarding:user-onboarding-needs-onboarding')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Invited user should NOT need onboarding
        self.assertFalse(data['needs_onboarding'])
        self.assertTrue(data['skip_onboarding'])
        self.assertEqual(data['reason'], 'invited_user')
        self.assertEqual(data['required_steps'], 0)
        self.assertEqual(data['completed_required_steps'], 0)
        self.assertEqual(data['missing_steps'], [])
        self.assertFalse(data['is_finalized'])

    def test_user_with_completed_onboarding(self):
        """Test that a user who completed onboarding doesn't need it"""
        # Create a user
        completed_user = User.objects.create_user(
            email='completed@test.com',
            username='completed',
            password='testpass123'
        )

        UserProfile.objects.create(
            user=completed_user,
            skip_onboarding=False
        )

        # Create finalized step
        finalized_step = OnboardingStep.objects.create(
            name='finalized',
            title='Onboarding Finalized',
            step_order=999,
            is_active=False
        )

        # Create completed onboarding record
        UserOnboarding.objects.create(
            user_email=completed_user.email,
            step=finalized_step,
            status='completed'
        )

        self.client.force_authenticate(user=completed_user)

        url = reverse('onboarding:user-onboarding-needs-onboarding')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # User with completed onboarding should not need it
        self.assertFalse(data['needs_onboarding'])
        self.assertFalse(data['skip_onboarding'])
        self.assertEqual(data['reason'], 'finalization_check')
        self.assertTrue(data['is_finalized'])

    def test_user_without_profile_gets_default(self):
        """Test that a user without profile gets one created with skip_onboarding=False"""
        # Create user without profile
        no_profile_user = User.objects.create_user(
            email='noprofile@test.com',
            username='noprofile',
            password='testpass123'
        )

        # Verify no profile exists
        self.assertFalse(UserProfile.objects.filter(user=no_profile_user).exists())

        self.client.force_authenticate(user=no_profile_user)

        url = reverse('onboarding:user-onboarding-needs-onboarding')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Should create profile with skip_onboarding=False
        self.assertTrue(UserProfile.objects.filter(user=no_profile_user).exists())
        profile = UserProfile.objects.get(user=no_profile_user)
        self.assertFalse(profile.skip_onboarding)

        # User should need onboarding
        self.assertTrue(data['needs_onboarding'])
        self.assertFalse(data['skip_onboarding'])

    @patch('apps.companies.models.Company.objects')
    def test_invitation_flow_integration(self, mock_company):
        """Test the complete invitation flow sets skip_onboarding correctly"""
        # This test simulates what happens when a user registers with invitation_token

        # Create invitation
        invitation = TeamInvitation.objects.create(
            email='newmember@test.com',
            company=self.test_company,
            role=self.user_role,
            invited_by=self.owner_user,
            status='pending'
        )

        # Create user with invitation (simulating registration flow)
        new_user = User.objects.create_user(
            email='newmember@test.com',
            username='newmember',
            password='testpass123'
        )

        # Simulate the invitation acceptance flow
        # (This would normally happen in the accounts view during registration)
        UserProfile.objects.create(
            user=new_user,
            skip_onboarding=True  # This is what should happen during invitation acceptance
        )

        # Accept the invitation
        invitation.accept(new_user)

        # Test the onboarding endpoint
        self.client.force_authenticate(user=new_user)

        url = reverse('onboarding:user-onboarding-needs-onboarding')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # User should skip onboarding
        self.assertFalse(data['needs_onboarding'])
        self.assertTrue(data['skip_onboarding'])
        self.assertEqual(data['reason'], 'invited_user')

        # Verify invitation was accepted
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, 'accepted')
        self.assertEqual(invitation.accepted_by, new_user)


class OnboardingViewSetTestCase(TestCase):
    """Test other onboarding functionality"""

    def setUp(self):
        self.client = APIClient()

        self.user = User.objects.create_user(
            email='test@example.com',
            username='testuser',
            password='testpass123'
        )

        UserProfile.objects.create(
            user=self.user,
            skip_onboarding=False
        )

        self.client.force_authenticate(user=self.user)

    def test_needs_onboarding_endpoint_exists(self):
        """Test that the needs_onboarding endpoint is accessible"""
        url = reverse('onboarding:user-onboarding-needs-onboarding')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Response should have expected keys
        data = response.json()
        expected_keys = ['needs_onboarding', 'skip_onboarding', 'required_steps',
                        'completed_required_steps', 'missing_steps', 'is_finalized']

        for key in expected_keys:
            self.assertIn(key, data)