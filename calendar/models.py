from django.db import models
from django.core.exceptions import ValidationError

class SubscriptionCalendar(models.Model):
    customer = models.ForeignKey('Customer', on_delete=models.CASCADE)
    seal_subscription_id = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['seal_subscription_id']),
            models.Index(fields=['customer']),
            models.Index(fields=['created_at']),
        ]
    
    def clean(self):
        if not self.seal_subscription_id:
            raise ValidationError("Seal subscription ID is required")
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

class CalendarItem(models.Model):
    calendar = models.ForeignKey(
        SubscriptionCalendar,
        related_name='calendar_items',
        on_delete=models.CASCADE
    )
    delivery_date = models.DateField()
    product_variant_id = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(default=1)
    status = models.CharField(
        max_length=20,
        choices=[
            ('scheduled', 'Scheduled'),
            ('skipped', 'Skipped'),
            ('processed', 'Processed')
        ],
        default='scheduled'
    )
    
    class Meta:
        indexes = [
            models.Index(fields=['delivery_date']),
            models.Index(fields=['status']),
        ]
        ordering = ['delivery_date']