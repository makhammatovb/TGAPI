# Generated by Django 5.0.6 on 2024-07-08 09:47

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('telegram_api', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='telegramgroups',
            name='username',
            field=models.CharField(max_length=100),
        ),
    ]
