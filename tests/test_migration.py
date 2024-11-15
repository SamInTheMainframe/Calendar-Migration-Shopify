from django.test import TestCase
from django.utils import timezone
from unittest.mock import patch, MagicMock
from migration_plan import (
    migrate_subscription_data,
    transform_to_seal_format,
    map_billing_interval,
    map_products
)
from calendar.models import SubscriptionCalendar, CalendarItem
from datetime import datetime, timedelta

class MigrationTests(TestCase):
    def setUp(self):
        # Create test customer
        self.customer_id = "cust_123"
        
        # Create test subscription calendar
        self.calendar = SubscriptionCalendar.objects.create(
            customer_id=self.customer_id,
            seal_subscription_id=""
        )
        
        # Create test calendar items
        self.calendar_items = []
        start_date = timezone.now()
        for i in range(3):
            item = CalendarItem.objects.create(
                calendar=self.calendar,
                delivery_date=start_date + timedelta(days=30 * i),
                product_variant_id=f"variant_{i}",
                quantity=1,
                status='scheduled'
            )
            self.calendar_items.append(item)
        
        # Mock Seal API response
        self.mock_seal_response = {
            'id': 'seal_sub_123',
            'status': 'active',
            'customer_id': self.customer_id
        }

    @patch('services.seal_integration.SealSubscriptionService')
    def test_migration_success(self, mock_seal_service):
        # Configure mock
        mock_instance = mock_seal_service.return_value
        mock_instance.create_subscription.return_value = self.mock_seal_response
        
        # Run migration
        migrate_subscription_data('fake_api_key', 'fake_shop_url')
        
        # Verify calendar was updated
        updated_calendar = SubscriptionCalendar.objects.get(id=self.calendar.id)
        self.assertEqual(updated_calendar.seal_subscription_id, 'seal_sub_123')
        
        # Verify Seal service was called correctly
        mock_instance.create_subscription.assert_called_once()
        
    def test_transform_to_seal_format(self):
        test_subscription = {
            'customer_id': self.customer_id,
            'billing_interval': 'monthly',
            'products': [
                {
                    'product_variant_id': 'variant_1',
                    'quantity': 1,
                    'price': 1999
                }
            ]
        }
        
        transformed = transform_to_seal_format([test_subscription])
        
        self.assertEqual(len(transformed), 1)
        self.assertEqual(
            transformed[0]['billing_interval'],
            {'interval': 'month', 'interval_count': 1}
        )
        
    @patch('services.seal_integration.SealSubscriptionService')
    def test_migration_error_handling(self, mock_seal_service):
        # Configure mock to raise exception
        mock_instance = mock_seal_service.return_value
        mock_instance.create_subscription.side_effect = Exception("API Error")
        
        # Run migration
        with self.assertLogs(level='ERROR') as log:
            migrate_subscription_data('fake_api_key', 'fake_shop_url')
            
        # Verify error was logged
        self.assertIn('API Error', log.output[0])
        
        # Verify calendar wasn't updated
        updated_calendar = SubscriptionCalendar.objects.get(id=self.calendar.id)
        self.assertEqual(updated_calendar.seal_subscription_id, "")

    def test_map_billing_interval(self):
        test_cases = [
            ('monthly', {'interval': 'month', 'interval_count': 1}),
            ('bimonthly', {'interval': 'month', 'interval_count': 2}),
            ('quarterly', {'interval': 'month', 'interval_count': 3}),
        ]
        
        for input_interval, expected_output in test_cases:
            result = map_billing_interval({'billing_interval': input_interval})
            self.assertEqual(result, expected_output)

    def test_map_products(self):
        test_products = [
            {
                'product_variant_id': 'var_1',
                'quantity': 2,
                'price': 1999
            }
        ]
        
        result = map_products({'products': test_products})
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['variant_id'], 'var_1')
        self.assertEqual(result[0]['quantity'], 2)
        self.assertEqual(result[0]['price'], 1999)