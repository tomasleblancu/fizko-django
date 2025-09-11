# Migration to remove taxpayer field from Company model

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0003_add_taxpayer_reference'),
        ('taxpayers', '0006_reverse_taxpayer_company_relationship'),
    ]

    operations = [
        # Remove the taxpayer field from Company since TaxPayer now has company field
        migrations.RemoveField(
            model_name='company',
            name='taxpayer',
        ),
    ]