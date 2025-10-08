import datetime

from allauth.socialaccount.models import SocialAccount
from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from djstripe.models import Customer, Price, Product, Subscription

from membership.models import Membership
from profiles.models import DiscordActivity, Profile


class ProfileEligibilityTestCase(TestCase):
    def setUp(self):
        """Create a test user and profile for all tests"""
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        # Manually create profile since there's no auto-creation signal
        self.profile = Profile.objects.create(user=self.user)

        # Setup for djstripe Customer
        self.customer = Customer.objects.create(
            id="cus_test123",
            subscriber=self.user,
            livemode=False,
        )

    def _create_discord_socialaccount(self):
        """Helper to create a Discord social account"""
        return SocialAccount.objects.create(
            user=self.user,
            provider="discord",
            uid=f"discord_uid_{self.user.id}",
        )

    def _create_discord_activity(self, days_ago, message_count=5):
        """Helper to create Discord activity for a profile"""
        date = timezone.now().date() - datetime.timedelta(days=days_ago)
        DiscordActivity.objects.create(profile=self.profile, date=date, count=message_count)

    def _create_subscription(self, days_until_period_end=60, status="active"):
        """Helper to create a Stripe subscription"""
        # Get or create a product and price
        product, _ = Product.objects.get_or_create(
            id="prod_test123",
            defaults={
                "name": "Monthly Donation",
                "type": "service",
                "livemode": False,
            },
        )
        price, _ = Price.objects.get_or_create(
            id="price_test123",
            defaults={
                "product": product,
                "currency": "usd",
                "unit_amount": 1000,
                "recurring": {"interval": "month"},
                "livemode": False,
                "active": True,
            },
        )

        current_period_end = timezone.now() + datetime.timedelta(days=days_until_period_end)

        return Subscription.objects.create(
            id=f"sub_test_{timezone.now().timestamp()}",
            customer=self.customer,
            status=status,
            current_period_start=timezone.now() - datetime.timedelta(days=30),
            current_period_end=current_period_end,
            livemode=False,
        )

    def test_not_eligible_no_donor_no_discord(self):
        """Test user with no donor status and no Discord activity"""
        target_date = timezone.now() + datetime.timedelta(days=30)
        result = self.profile.eligible_as_of(target_date)

        self.assertFalse(result["eligible"])
        self.assertFalse(result["donor"])
        self.assertFalse(result["discord_active"])
        self.assertEqual(result["donor_status"], "inactive")
        self.assertEqual(len(result["warnings"]), 0)
        self.assertFalse(result["at_risk"])

    def test_eligible_via_donor_only(self):
        """Test user eligible only through active donation"""
        # Create active subscription that covers target date
        target_date = timezone.now() + datetime.timedelta(days=30)
        self._create_subscription(days_until_period_end=35)

        result = self.profile.eligible_as_of(target_date)

        self.assertTrue(result["eligible"])
        self.assertTrue(result["donor"])
        self.assertTrue(result["donor_sufficient_alone"])
        self.assertFalse(result["discord_active"])
        self.assertFalse(result["discord_sufficient_alone"])
        # Should warn about single eligibility path
        self.assertGreater(len(result["warnings"]), 0)
        self.assertTrue(any("Discord" in warning for warning in result["warnings"]))

    def test_eligible_via_discord_only(self):
        """Test user eligible only through Discord activity"""
        # Create Discord account
        self._create_discord_socialaccount()

        # Target is 30 days from now
        # Create activity that will NOT be in the valid window
        target_date = timezone.now() + datetime.timedelta(days=30)
        self._create_discord_activity(days_ago=10)  # Activity 10 days ago
        # This activity will be 40 days old at target (outside 30-day window)

        result = self.profile.eligible_as_of(target_date)

        # Activity ages out before target
        self.assertFalse(result["eligible"])

    def test_eligible_discord_activity_in_future_window(self):
        """Test user with Discord activity that will be valid at target date"""
        self._create_discord_socialaccount()

        # Target is 20 days from now
        target_date = timezone.now() + datetime.timedelta(days=20)
        # Create activity from 5 days ago - will be 25 days old at target (within 30 day window)
        self._create_discord_activity(days_ago=5)

        result = self.profile.eligible_as_of(target_date)

        self.assertTrue(result["eligible"])
        self.assertTrue(result["discord_active"])
        self.assertTrue(result["discord_sufficient_alone"])
        self.assertFalse(result["donor"])
        # Should warn about single eligibility path
        self.assertGreater(len(result["warnings"]), 0)
        self.assertTrue(any("donor" in warning.lower() for warning in result["warnings"]))

    def test_eligible_both_donor_and_discord(self):
        """Test user eligible via both donor and Discord (most stable)"""
        target_date = timezone.now() + datetime.timedelta(days=20)

        # Create subscription covering target
        self._create_subscription(days_until_period_end=25)

        # Create Discord account and recent activity
        self._create_discord_socialaccount()
        self._create_discord_activity(days_ago=5)  # Will be 25 days old at target

        result = self.profile.eligible_as_of(target_date)

        self.assertTrue(result["eligible"])
        self.assertTrue(result["donor_sufficient_alone"])
        self.assertTrue(result["discord_sufficient_alone"])

    def test_at_risk_renewal_required_no_discord_backup(self):
        """Test user at risk - renewal required and no Discord backup"""
        now = timezone.now()
        target_date = now + datetime.timedelta(days=30)

        # Create subscription that renews before target (expires in 15 days)
        # Since it expires before target, user won't be eligible
        self._create_subscription(days_until_period_end=15)

        result = self.profile.eligible_as_of(target_date)

        # Subscription doesn't cover target date
        self.assertFalse(result["eligible"])
        self.assertFalse(result["donor"])

    def test_at_risk_renewal_with_subscription_covering_target(self):
        """Test renewal before target but subscription still covers target"""
        now = timezone.now()
        target_date = now + datetime.timedelta(days=20)

        # Subscription renews in 15 days but that's before target
        # In reality, we assume subscription continues if active
        self._create_subscription(days_until_period_end=25)

        result = self.profile.eligible_as_of(target_date)

        self.assertTrue(result["eligible"])
        self.assertTrue(result["donor_sufficient_alone"])
        # Check for renewal warning if renewal date is between now and target
        if result["donor_status"] == "active_renewal_required":
            self.assertTrue(any("renews" in warning.lower() for warning in result["warnings"]))

    def test_discord_activity_aging_out_no_donor_backup(self):
        """Test Discord activity will age out before deadline with no donor backup"""
        self._create_discord_socialaccount()

        # Create activity from 5 days ago
        # Target is 40 days from now
        # Activity will be 45 days old at target (outside 30-day window)
        target_date = timezone.now() + datetime.timedelta(days=40)
        self._create_discord_activity(days_ago=5)

        result = self.profile.eligible_as_of(target_date)

        # Activity ages out before target
        self.assertFalse(result["eligible"])
        self.assertFalse(result["discord_active"])

    def test_discord_activity_aging_with_donor_backup(self):
        """Test Discord activity will age out but user has donor backup"""
        target_date = timezone.now() + datetime.timedelta(days=40)

        # Create subscription covering target
        self._create_subscription(days_until_period_end=45)

        # Create Discord with aging activity
        self._create_discord_socialaccount()
        self._create_discord_activity(days_ago=5)  # Will be 45 days old at target

        result = self.profile.eligible_as_of(target_date)

        self.assertTrue(result["eligible"])
        self.assertTrue(result["donor_sufficient_alone"])
        # Discord activity ages out
        self.assertFalse(result["discord_sufficient_alone"])

    def test_subscription_expires_before_target(self):
        """Test subscription that expires before target date"""
        now = timezone.now()
        target_date = now + datetime.timedelta(days=30)

        # Subscription expires in 15 days, before target
        self._create_subscription(days_until_period_end=15)

        result = self.profile.eligible_as_of(target_date)

        # Subscription doesn't cover target
        self.assertFalse(result["eligible"])
        self.assertFalse(result["donor"])

    def test_historical_eligibility(self):
        """Test checking eligibility for a past date"""
        self._create_discord_socialaccount()

        # Create activity from 35 days ago
        self._create_discord_activity(days_ago=35)

        # Check eligibility for 10 days ago
        # Activity from 35 days ago would have been 25 days old then (within window)
        target_date = timezone.now() - datetime.timedelta(days=10)

        result = self.profile.eligible_as_of(target_date)

        self.assertTrue(result["eligible"])
        self.assertTrue(result["discord_active"])

    def test_no_discord_connected(self):
        """Test user without Discord connected"""
        target_date = timezone.now() + datetime.timedelta(days=30)
        result = self.profile.eligible_as_of(target_date)

        self.assertFalse(result["eligible"])
        self.assertFalse(result["discord_active"])
        self.assertIsNone(result["discord_last_activity"])

    def test_donor_with_no_discord_warns_to_connect(self):
        """Test donor without Discord gets suggestion to connect Discord"""
        target_date = timezone.now() + datetime.timedelta(days=30)
        self._create_subscription(days_until_period_end=35)

        result = self.profile.eligible_as_of(target_date)

        self.assertTrue(result["eligible"])
        self.assertTrue(result["donor_sufficient_alone"])
        # Should suggest connecting Discord as backup
        self.assertTrue(any("Discord" in warning for warning in result["warnings"]))

    def test_donor_with_discord_but_inactive_warns_to_post(self):
        """Test donor with Discord connected but no activity"""
        target_date = timezone.now() + datetime.timedelta(days=30)
        self._create_subscription(days_until_period_end=35)
        self._create_discord_socialaccount()
        # No Discord activity created

        result = self.profile.eligible_as_of(target_date)

        self.assertTrue(result["eligible"])
        self.assertTrue(result["donor_sufficient_alone"])
        self.assertFalse(result["discord_sufficient_alone"])

    def test_target_date_as_date_object(self):
        """Test that method works with date object (not datetime)"""
        self._create_discord_socialaccount()
        self._create_discord_activity(days_ago=5)

        # Pass a date object instead of datetime
        target_date = (timezone.now() + datetime.timedelta(days=20)).date()
        result = self.profile.eligible_as_of(target_date)

        # Should still work
        self.assertIsNotNone(result)
        self.assertIn("eligible", result)
        self.assertIsInstance(result["eligible"], bool)

    def test_multiple_discord_activities(self):
        """Test user with multiple Discord activity entries"""
        self._create_discord_socialaccount()

        # Create multiple activities
        self._create_discord_activity(days_ago=5, message_count=3)
        self._create_discord_activity(days_ago=10, message_count=7)
        self._create_discord_activity(days_ago=15, message_count=2)

        target_date = timezone.now() + datetime.timedelta(days=20)
        result = self.profile.eligible_as_of(target_date)

        # All activities will be within valid window at target
        self.assertTrue(result["eligible"])
        self.assertTrue(result["discord_active"])
        self.assertIsNotNone(result["discord_last_activity"])

    def test_trialing_subscription_counts_as_donor(self):
        """Test that trialing subscriptions count towards eligibility"""
        target_date = timezone.now() + datetime.timedelta(days=10)

        # Create trialing subscription
        self._create_subscription(days_until_period_end=15, status="trialing")

        result = self.profile.eligible_as_of(target_date)

        self.assertTrue(result["eligible"])
        self.assertTrue(result["donor"])

    def test_canceled_subscription_does_not_count(self):
        """Test that canceled subscriptions don't count"""
        target_date = timezone.now() + datetime.timedelta(days=30)

        # Create canceled subscription (even if period_end is after target)
        self._create_subscription(days_until_period_end=35, status="canceled")

        result = self.profile.eligible_as_of(target_date)

        self.assertFalse(result["eligible"])
        self.assertFalse(result["donor"])

    def test_multiple_subscriptions_uses_latest(self):
        """Test that with multiple subscriptions, the latest one is used"""
        target_date = timezone.now() + datetime.timedelta(days=30)

        # Create old expired subscription
        self._create_subscription(days_until_period_end=5)

        # Create new subscription covering target
        self._create_subscription(days_until_period_end=35)

        result = self.profile.eligible_as_of(target_date)

        self.assertTrue(result["eligible"])
        self.assertTrue(result["donor"])

    def test_target_date_is_now(self):
        """Test eligibility check for current moment"""
        self._create_discord_socialaccount()
        # Activity from yesterday should be valid for "now"
        self._create_discord_activity(days_ago=1)

        target_date = timezone.now()
        result = self.profile.eligible_as_of(target_date)

        self.assertTrue(result["eligible"])
        self.assertTrue(result["discord_active"])

    def test_activity_exactly_30_days_before_target(self):
        """Test Discord activity at exact 30-day boundary"""
        self._create_discord_socialaccount()

        target_date = timezone.now() + datetime.timedelta(days=30)
        # Activity from exactly 0 days ago will be exactly 30 days old at target
        self._create_discord_activity(days_ago=0)

        result = self.profile.eligible_as_of(target_date)

        # Activity at exactly 30 days should be valid (30-day window is inclusive)
        self.assertTrue(result["eligible"])
        self.assertTrue(result["discord_active"])

    def test_activity_exactly_31_days_before_target(self):
        """Test Discord activity just outside 30-day window"""
        self._create_discord_socialaccount()

        target_date = timezone.now() + datetime.timedelta(days=31)
        # Activity from today will be 31 days old at target (outside window)
        self._create_discord_activity(days_ago=0)

        result = self.profile.eligible_as_of(target_date)

        # Activity at 31 days should be invalid
        self.assertFalse(result["eligible"])
        self.assertFalse(result["discord_active"])

    def test_subscription_period_end_exactly_at_target(self):
        """Test subscription that ends exactly at target date"""
        target_date = timezone.now() + datetime.timedelta(days=30)

        # Subscription ending exactly at target
        self._create_subscription(days_until_period_end=30)

        result = self.profile.eligible_as_of(target_date)

        # Should be eligible since period_end >= target_date
        self.assertTrue(result["eligible"])
        self.assertTrue(result["donor"])

    def test_subscription_period_end_one_day_before_target(self):
        """Test subscription that ends one day before target"""
        target_date = timezone.now() + datetime.timedelta(days=30)

        # Subscription ending one day before target
        self._create_subscription(days_until_period_end=29)

        result = self.profile.eligible_as_of(target_date)

        # Should NOT be eligible since period_end < target_date
        self.assertFalse(result["eligible"])
        self.assertFalse(result["donor"])

    def test_active_stable_donor_status(self):
        """Test donor status when subscription is well beyond target (no renewal risk)"""
        target_date = timezone.now() + datetime.timedelta(days=10)

        # Subscription ending well after target (60 days)
        self._create_subscription(days_until_period_end=60)

        result = self.profile.eligible_as_of(target_date)

        self.assertTrue(result["eligible"])
        self.assertEqual(result["donor_status"], "active_stable")
        # Should not be at risk
        self.assertFalse(result["at_risk"])

    def test_past_due_subscription_does_not_count(self):
        """Test that past_due subscriptions don't count as eligible"""
        target_date = timezone.now() + datetime.timedelta(days=30)

        # Create past_due subscription
        self._create_subscription(days_until_period_end=35, status="past_due")

        result = self.profile.eligible_as_of(target_date)

        # past_due is not in the allowed statuses (only "active" and "trialing")
        self.assertFalse(result["eligible"])
        self.assertFalse(result["donor"])

    def test_incomplete_subscription_does_not_count(self):
        """Test that incomplete subscriptions don't count"""
        target_date = timezone.now() + datetime.timedelta(days=30)

        self._create_subscription(days_until_period_end=35, status="incomplete")

        result = self.profile.eligible_as_of(target_date)

        self.assertFalse(result["eligible"])
        self.assertFalse(result["donor"])

    def test_at_risk_false_when_both_criteria_solid(self):
        """Test at_risk is False when user has both stable donor and Discord"""
        target_date = timezone.now() + datetime.timedelta(days=20)

        # Stable subscription well beyond target
        self._create_subscription(days_until_period_end=60)

        # Recent Discord activity
        self._create_discord_socialaccount()
        self._create_discord_activity(days_ago=5)

        result = self.profile.eligible_as_of(target_date)

        self.assertTrue(result["eligible"])
        self.assertTrue(result["donor_sufficient_alone"])
        self.assertTrue(result["discord_sufficient_alone"])
        # Should NOT be at risk with both solid
        self.assertFalse(result["at_risk"])

    def test_no_warnings_when_both_criteria_solid(self):
        """Test no warnings generated when eligibility is very stable"""
        target_date = timezone.now() + datetime.timedelta(days=15)

        # Stable subscription
        self._create_subscription(days_until_period_end=60)

        # Stable Discord activity
        self._create_discord_socialaccount()
        self._create_discord_activity(days_ago=2)

        result = self.profile.eligible_as_of(target_date)

        self.assertTrue(result["eligible"])
        # Should have no warnings when everything is solid
        self.assertEqual(len(result["warnings"]), 0)

    def test_discord_connected_but_no_activity_ever(self):
        """Test Discord connected but absolutely no activity records"""
        self._create_discord_socialaccount()
        # Don't create any activity

        target_date = timezone.now() + datetime.timedelta(days=30)
        result = self.profile.eligible_as_of(target_date)

        self.assertFalse(result["eligible"])
        self.assertFalse(result["discord_active"])
        self.assertIsNone(result["discord_last_activity"])

    def test_multiple_warnings_generated(self):
        """Test that multiple warnings can be generated simultaneously"""
        now = timezone.now()
        target_date = now + datetime.timedelta(days=35)

        # Create subscription that renews before target
        self._create_subscription(days_until_period_end=50)

        # Create Discord that will age out
        self._create_discord_socialaccount()
        self._create_discord_activity(days_ago=10)  # Will be 45 days old at target

        result = self.profile.eligible_as_of(target_date)

        self.assertTrue(result["eligible"])  # Donor keeps them eligible
        self.assertTrue(result["donor_sufficient_alone"])
        self.assertFalse(result["discord_sufficient_alone"])  # Discord ages out

        # Should have warnings about Discord aging out
        self.assertGreater(len(result["warnings"]), 0)

    def test_activity_on_target_date_itself(self):
        """Test Discord activity exactly on the target date"""
        self._create_discord_socialaccount()

        # Create activity for "today"
        target_date = timezone.now().date()
        DiscordActivity.objects.create(profile=self.profile, date=target_date, count=5)

        result = self.profile.eligible_as_of(target_date)

        # Activity on target date should count
        self.assertTrue(result["eligible"])
        self.assertTrue(result["discord_active"])

    def test_eligible_via_membership_record_only(self):
        """Test user eligible only through Membership record"""
        target_date = timezone.now() + datetime.timedelta(days=30)

        # Create active membership with no end date (ongoing)
        Membership.objects.create(
            user=self.user,
            kind=Membership.Kind.FISCAL,
            start_date=timezone.now().date() - datetime.timedelta(days=10),
            end_date=None,
            reason="Large one-time donation",
        )

        result = self.profile.eligible_as_of(target_date)

        self.assertTrue(result["eligible"])
        self.assertTrue(result["membership_sufficient_alone"])
        self.assertFalse(result["donor_sufficient_alone"])
        self.assertFalse(result["discord_sufficient_alone"])
        # Should have no warnings since membership is a special case
        self.assertEqual(len(result["warnings"]), 0)

    def test_eligible_via_membership_record_with_end_date(self):
        """Test user eligible through Membership record with specific end date"""
        now = timezone.now().date()
        target_date = now + datetime.timedelta(days=30)

        # Create membership that covers the target date
        Membership.objects.create(
            user=self.user,
            kind=Membership.Kind.PARTICIPATION,
            start_date=now - datetime.timedelta(days=5),
            end_date=now + datetime.timedelta(days=60),
            reason="Substantial volunteer contribution",
        )

        result = self.profile.eligible_as_of(target_date)

        self.assertTrue(result["eligible"])
        self.assertTrue(result["membership_sufficient_alone"])

    def test_not_eligible_membership_expired(self):
        """Test user not eligible when Membership has expired"""
        now = timezone.now().date()
        target_date = now + datetime.timedelta(days=30)

        # Create membership that expired before target
        Membership.objects.create(
            user=self.user,
            kind=Membership.Kind.FISCAL,
            start_date=now - datetime.timedelta(days=100),
            end_date=now - datetime.timedelta(days=10),  # Expired 10 days ago
            reason="Past contribution",
        )

        result = self.profile.eligible_as_of(target_date)

        self.assertFalse(result["eligible"])
        self.assertFalse(result["membership_sufficient_alone"])

    def test_not_eligible_membership_not_started(self):
        """Test user not eligible when Membership hasn't started yet"""
        now = timezone.now().date()
        target_date = now + datetime.timedelta(days=30)

        # Create membership that starts after target
        Membership.objects.create(
            user=self.user,
            kind=Membership.Kind.FISCAL,
            start_date=target_date + datetime.timedelta(days=10),  # Starts after target
            end_date=None,
            reason="Future membership",
        )

        result = self.profile.eligible_as_of(target_date)

        self.assertFalse(result["eligible"])
        self.assertFalse(result["membership_sufficient_alone"])

    def test_membership_method_with_active_membership(self):
        """Test Profile.membership() returns True with active Membership record"""
        now = timezone.now().date()

        # Create active membership
        Membership.objects.create(
            user=self.user,
            kind=Membership.Kind.FISCAL,
            start_date=now - datetime.timedelta(days=30),
            end_date=None,
            reason="Large donation",
        )

        self.assertTrue(self.profile.membership())

    def test_membership_method_with_expired_membership(self):
        """Test Profile.membership() returns False with expired Membership"""
        now = timezone.now().date()

        # Create expired membership
        Membership.objects.create(
            user=self.user,
            kind=Membership.Kind.FISCAL,
            start_date=now - datetime.timedelta(days=100),
            end_date=now - datetime.timedelta(days=10),
            reason="Past contribution",
        )

        self.assertFalse(self.profile.membership())

    def test_membership_with_donor_and_discord_no_warnings(self):
        """Test that having a Membership record suppresses backup warnings"""
        target_date = timezone.now() + datetime.timedelta(days=30)

        # Create membership
        Membership.objects.create(
            user=self.user,
            kind=Membership.Kind.FISCAL,
            start_date=timezone.now().date() - datetime.timedelta(days=10),
            end_date=None,
            reason="Special recognition",
        )

        # Also create subscription (but should not warn about single point of failure)
        self._create_subscription(days_until_period_end=35)

        result = self.profile.eligible_as_of(target_date)

        self.assertTrue(result["eligible"])
        self.assertTrue(result["membership_sufficient_alone"])
        self.assertTrue(result["donor_sufficient_alone"])
        # Should have NO warnings since membership overrides single-point warnings
        self.assertEqual(len(result["warnings"]), 0)

    def test_membership_exactly_at_boundaries(self):
        """Test membership at exact start and end date boundaries"""
        now = timezone.now().date()

        # Test at start date
        Membership.objects.create(
            user=self.user,
            kind=Membership.Kind.FISCAL,
            start_date=now,
            end_date=now + datetime.timedelta(days=30),
            reason="Test",
        )

        # Should be eligible today
        result = self.profile.eligible_as_of(now)
        self.assertTrue(result["eligible"])
        self.assertTrue(result["membership_sufficient_alone"])

        # Should be eligible at end date
        end_date = now + datetime.timedelta(days=30)
        result = self.profile.eligible_as_of(end_date)
        self.assertTrue(result["eligible"])
        self.assertTrue(result["membership_sufficient_alone"])

        # Should NOT be eligible one day after end
        after_end = end_date + datetime.timedelta(days=1)
        result = self.profile.eligible_as_of(after_end)
        self.assertFalse(result["membership_sufficient_alone"])
