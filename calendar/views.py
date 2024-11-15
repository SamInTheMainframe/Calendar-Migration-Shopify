from django.db.models import Prefetch
from django.views.decorators.cache import cache_page
from django.core.paginator import Paginator
from django.http import JsonResponse
from services.seal_integration import SealSubscriptionService
from .models import SubscriptionCalendar, CalendarItem
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
import json
from typing import Dict, List
from django.utils import timezone
from django.conf import settings
from django.db import models
import logging

logger = logging.getLogger(__name__)

@cache_page(60 * 15)  # Cache for 15 minutes
def calendar_view(request, customer_id):
    page = request.GET.get('page', 1)
    items_per_page = 20
    
    # Optimize queries with select_related and prefetch_related
    calendar_query = SubscriptionCalendar.objects.select_related(
        'customer'
    ).prefetch_related(
        Prefetch(
            'calendar_items',
            queryset=CalendarItem.objects.filter(status='scheduled')
        )
    ).filter(
        customer_id=customer_id
    )
    
    # Implement pagination
    paginator = Paginator(calendar_query, items_per_page)
    calendar_page = paginator.get_page(page)
    
    # Format response data
    calendar_data = {
        'items': [
            {
                'id': item.id,
                'delivery_date': item.delivery_date,
                'product_variant_id': item.product_variant_id,
                'quantity': item.quantity,
                'status': item.status
            }
            for calendar in calendar_page
            for item in calendar.calendar_items.all()
        ],
        'pagination': {
            'current_page': calendar_page.number,
            'total_pages': paginator.num_pages,
            'has_next': calendar_page.has_next(),
            'has_previous': calendar_page.has_previous()
        }
    }
    
    return JsonResponse(calendar_data)

@csrf_exempt
@require_http_methods(["POST"])
def webhook_handler(request):
    """Handle webhooks from Seal Subscriptions"""
    try:
        data = json.loads(request.body)
        event_type = data.get('event_type')
        
        if event_type == 'subscription.updated':
            handle_subscription_update(data)
        elif event_type == 'subscription.cancelled':
            handle_subscription_cancellation(data)
            
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@require_http_methods(["POST"])
def update_calendar_item(request, item_id):
    """Update a calendar item"""
    try:
        item = CalendarItem.objects.get(id=item_id)
        data = json.loads(request.body)
        
        # Update calendar item
        item.delivery_date = data.get('delivery_date', item.delivery_date)
        item.quantity = data.get('quantity', item.quantity)
        item.status = data.get('status', item.status)
        item.save()
        
        # Sync with Seal if needed
        if data.get('sync_with_seal', False):
            sync_with_seal(item)
            
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

def handle_subscription_update(data: Dict) -> None:
    """Handle subscription update webhook from Seal"""
    try:
        subscription_id = data.get('subscription_id')
        calendar = SubscriptionCalendar.objects.get(
            seal_subscription_id=subscription_id
        )
        
        # Update calendar items based on subscription changes
        if 'next_delivery_date' in data:
            CalendarItem.objects.filter(
                calendar=calendar,
                status='scheduled'
            ).update(
                delivery_date=data['next_delivery_date']
            )
            
        if 'product_changes' in data:
            update_calendar_products(calendar, data['product_changes'])
            
    except SubscriptionCalendar.DoesNotExist:
        logger.error(f"Calendar not found for subscription {subscription_id}")
    except Exception as e:
        logger.error(f"Error handling subscription update: {str(e)}")

def handle_subscription_cancellation(data: Dict) -> None:
    """Handle subscription cancellation webhook from Seal"""
    try:
        subscription_id = data.get('subscription_id')
        calendar = SubscriptionCalendar.objects.get(
            seal_subscription_id=subscription_id
        )
        
        # Mark all future calendar items as cancelled
        CalendarItem.objects.filter(
            calendar=calendar,
            delivery_date__gte=timezone.now().date(),
            status='scheduled'
        ).update(status='cancelled')
        
    except SubscriptionCalendar.DoesNotExist:
        logger.error(f"Calendar not found for subscription {subscription_id}")
    except Exception as e:
        logger.error(f"Error handling subscription cancellation: {str(e)}")

def sync_with_seal(calendar_item: CalendarItem) -> None:
    """Sync calendar item changes with Seal subscription"""
    try:
        calendar = calendar_item.calendar
        seal_service = SealSubscriptionService(
            settings.SEAL_API_KEY,
            settings.SHOP_URL
        )
        
        # Prepare update data
        update_data = {
            'next_delivery_date': calendar_item.delivery_date.isoformat(),
            'products': [
                {
                    'variant_id': calendar_item.product_variant_id,
                    'quantity': calendar_item.quantity
                }
            ]
        }
        
        if calendar_item.status == 'skipped':
            update_data['skip_next_delivery'] = True
        
        # Update subscription in Seal
        seal_service.update_subscription(
            calendar.seal_subscription_id,
            update_data
        )
        
    except Exception as e:
        logger.error(f"Error syncing with Seal: {str(e)}")
        raise

def update_calendar_products(calendar: SubscriptionCalendar, product_changes: List[Dict]) -> None:
    """Update calendar items based on product changes"""
    try:
        for change in product_changes:
            CalendarItem.objects.filter(
                calendar=calendar,
                status='scheduled',
                product_variant_id=change['variant_id']
            ).update(
                quantity=change.get('quantity', models.F('quantity')),
                status=change.get('status', models.F('status'))
            )
    except Exception as e:
        logger.error(f"Error updating calendar products: {str(e)}")
        raise