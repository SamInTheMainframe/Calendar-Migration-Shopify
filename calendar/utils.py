from typing import Dict, Any, Optional
from datetime import datetime, date
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

def validate_calendar_item_data(data: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """Validate calendar item update data"""
    errors = {}
    
    if 'delivery_date' in data:
        try:
            delivery_date = datetime.fromisoformat(data['delivery_date']).date()
            if delivery_date < date.today():
                errors['delivery_date'] = "Delivery date cannot be in the past"
        except ValueError:
            errors['delivery_date'] = "Invalid date format"
    
    if 'quantity' in data:
        try:
            quantity = int(data['quantity'])
            if quantity < 1:
                errors['quantity'] = "Quantity must be positive"
        except ValueError:
            errors['quantity'] = "Invalid quantity"
    
    if 'status' in data and data['status'] not in ['scheduled', 'skipped', 'processed']:
        errors['status'] = "Invalid status"
    
    return errors if errors else None

def format_calendar_item(item: 'CalendarItem') -> Dict[str, Any]:
    """Format calendar item for API response"""
    return {
        'id': item.id,
        'delivery_date': item.delivery_date.isoformat(),
        'product_variant_id': item.product_variant_id,
        'quantity': item.quantity,
        'status': item.status,
        'created_at': item.calendar.created_at.isoformat(),
        'updated_at': item.calendar.updated_at.isoformat()
    } 