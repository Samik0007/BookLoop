from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Order',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('user', models.CharField(max_length=20, null=True)),
                ('date_ordered', models.DateTimeField(auto_now_add=True)),
                ('complete', models.BooleanField(default=False)),
                ('payment_method', models.CharField(choices=[('Cash On Delivery', 'Cash On Delivery'), ('Khalti Pay', 'Khalti Pay')], default='Cash On Delivery', max_length=20)),
                ('order_status', models.CharField(choices=[('Order Received', 'Order Received'), ('Order Processing', 'Order Processing'), ('On the way', 'On the way'), ('Order Completed', 'Order Completed'), ('Order Canceled', 'Order Canceled')], default='Order Received', max_length=50)),
                ('transaction_id', models.CharField(max_length=200, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='Product',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('Book_name', models.CharField(max_length=50)),
                ('Author', models.CharField(default='', max_length=50)),
                ('genre', models.CharField(max_length=300)),
                ('description', models.CharField(default='', max_length=1000)),
                ('price', models.IntegerField(default=0)),
                ('pub_date', models.DateField(default=django.utils.timezone.now)),
                ('quantity', models.PositiveBigIntegerField(default=1)),
                ('image', models.ImageField(blank=True, null=True, upload_to='books/images')),
                ('sequence', models.IntegerField(default=0)),
            ],
        ),
        migrations.CreateModel(
            name='Wishlist',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('user', models.CharField(max_length=20)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('product', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='books.product')),
            ],
        ),
        migrations.CreateModel(
            name='ShippingAddress',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('user', models.CharField(max_length=20, null=True)),
                ('address', models.CharField(max_length=100)),
                ('city', models.CharField(choices=[('Kathmandu', 'Kathmandu'), ('Bhaktapur', 'Bhaktapur'), ('Lalitpur', 'Lalitpur')], max_length=100)),
                ('ward_no', models.IntegerField()),
                ('zip_code', models.IntegerField()),
                ('phone', models.IntegerField()),
                ('date_added', models.DateTimeField(auto_now_add=True)),
                ('rating', models.FloatField(default=0)),
                ('order', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='books.order')),
            ],
        ),
        migrations.CreateModel(
            name='OrderItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.IntegerField(default=0)),
                ('date_added', models.DateTimeField(auto_now_add=True)),
                ('Book_name', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='books.product')),
                ('order', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='books.order')),
            ],
        ),
    ]
