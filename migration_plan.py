from typing import Dict, List
from services.seal_integration import SealSubscriptionService
from calendar.models import SubscriptionCalendar

def migrate_subscription_data(seal_api_key: str, shop_url: str):
    """Handles the complete migration process"""
    seal_service = SealSubscriptionService(seal_api_key, shop_url)
    
    # Step 1: Export existing data
    existing_subscriptions = export_current_subscriptions()
    
    # Step 2: Transform data
    seal_formatted_data = transform_to_seal_format(existing_subscriptions)
    
    # Step 3: Import to Seal
    for subscription_data in seal_formatted_data:
        try:
            # Create subscription in Seal
            seal_subscription = seal_service.create_subscription(subscription_data)
            
            # Update calendar with new Seal subscription ID
            update_calendar_reference(
                subscription_data['customer_id'],
                seal_subscription['id']
            )
        except Exception as e:
            log_migration_error(subscription_data, str(e))

def export_current_subscriptions() -> List[Dict]:
    """Export existing subscription data"""
    return SubscriptionCalendar.objects.select_related(
        'customer'
    ).prefetch_related(
        'calendar_items'
    ).values(
        'customer_id',
        'subscription_details',
        'calendar_selections'
    )

def transform_to_seal_format(subscriptions: List[Dict]) -> List[Dict]:
    """Transform data to match Seal's format"""
    transformed_data = []
    for sub in subscriptions:
        transformed = {
            'customer_id': sub['customer_id'],
            'billing_interval': map_billing_interval(sub),
            'products': map_products(sub),
            'next_billing_date': calculate_next_billing_date(sub),
            # Add other required Seal fields
        }
        transformed_data.append(transformed)
    return transformed_data 

def map_billing_interval(subscription: Dict) -> Dict:
    """Map existing billing interval to Seal format"""
    interval_mapping = {
        'monthly': {'interval': 'month', 'interval_count': 1},
        'bimonthly': {'interval': 'month', 'interval_count': 2},
        'quarterly': {'interval': 'month', 'interval_count': 3},
        # Add other mappings as needed
    }
    return interval_mapping.get(subscription['billing_interval'])

def map_products(subscription: Dict) -> List[Dict]:
    """Map product data to Seal format"""
    return [{
        'variant_id': item['product_variant_id'],
        'quantity': item['quantity'],
        'price': item['price']  # Ensure price handling matches Seal's requirements
    } for item in subscription['products']]

def calculate_next_billing_date(subscription: Dict) -> str:
    """Calculate next billing date based on current subscription"""
    from datetime import datetime, timedelta
    
    # Get the last billing date or use current date if not available
    last_billing_date = subscription.get('last_billing_date')
    if last_billing_date:
        last_date = datetime.fromisoformat(last_billing_date.rstrip('Z'))
    else:
        last_date = datetime.now()
    
    # Get billing interval
    interval = map_billing_interval(subscription)
    
    # Calculate next date based on interval
    if interval['interval'] == 'month':
        next_date = last_date + timedelta(days=30 * interval['interval_count'])
    else:
        # Add other interval calculations as needed
        raise ValueError(f"Unsupported interval: {interval['interval']}")
    
    return next_date.isoformat()

def update_calendar_reference(customer_id: str, seal_subscription_id: str) -> None:
    """Update calendar with new Seal subscription ID"""
    SubscriptionCalendar.objects.filter(
        customer_id=customer_id
    ).update(
        seal_subscription_id=seal_subscription_id
    )

def log_migration_error(subscription_data: Dict, error: str) -> None:
    """Log migration errors for later review"""
    import logging
    logger = logging.getLogger(__name__)
    
    error_message = (
        f"Migration failed for customer {subscription_data['customer_id']}: "
        f"{error}"
    )
    
    # Log to file
    logger.error(error_message)
    
    # Could also log to database if needed
    # MigrationError.objects.create(
    #     customer_id=subscription_data['customer_id'],
    #     error_message=error,
    #     subscription_data=subscription_data
    # ) 