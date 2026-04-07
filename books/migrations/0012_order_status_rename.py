# Migration: rename order status stored values to the new 4-step tracking flow.
#
# Old → New
#   "Order Received"   → "Order Pending"    (order just placed)
#   "Order Processing" → "Order Dispatched" (admin processed and sent)
#   "On the way"       → "Order On the Way" (in transit)
#   "Order Completed"  → "Order Received"   (customer received)
#   "Order Canceled"   → "Order Canceled"   (unchanged)
#
# Also updates the field default from "Order Received" → "Order Pending".

from django.db import migrations, models

STATUS_MAP = {
    "Order Received":   "Order Pending",
    "Order Processing": "Order Dispatched",
    "On the way":       "Order On the Way",
    "Order Completed":  "Order Received",
    # "Order Canceled" stays unchanged
}

REVERSE_MAP = {v: k for k, v in STATUS_MAP.items()}


def migrate_forward(apps, schema_editor):
    Order = apps.get_model("books", "Order")
    for old, new in STATUS_MAP.items():
        Order.objects.filter(order_status=old).update(order_status=new)


def migrate_backward(apps, schema_editor):
    Order = apps.get_model("books", "Order")
    for new, old in REVERSE_MAP.items():
        Order.objects.filter(order_status=new).update(order_status=old)


class Migration(migrations.Migration):

    dependencies = [
        ("books", "0011_pendingbook"),
    ]

    operations = [
        # 1. Remap existing rows first (data must be valid before AlterField)
        migrations.RunPython(migrate_forward, reverse_code=migrate_backward),

        # 2. Update choices and default on the field
        migrations.AlterField(
            model_name="order",
            name="order_status",
            field=models.CharField(
                max_length=50,
                choices=[
                    ("Order Pending",    "Order Pending"),
                    ("Order Dispatched", "Order Dispatched"),
                    ("Order On the Way", "Order On the Way"),
                    ("Order Received",   "Order Received"),
                    ("Order Canceled",   "Order Canceled"),
                ],
                default="Order Pending",
            ),
        ),
    ]
