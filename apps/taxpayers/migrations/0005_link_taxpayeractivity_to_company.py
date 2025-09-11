# Generated migration for linking TaxpayerActivity to Company

from django.db import migrations, models
import django.db.models.deletion


def migrate_activity_data_forward(apps, schema_editor):
    """Migrate existing TaxpayerActivity data to link with companies"""
    Company = apps.get_model('companies', 'Company')
    TaxpayerActivity = apps.get_model('taxpayers', 'TaxpayerActivity')
    
    # If there are existing activities without company, try to link them or delete them
    activities_without_company = TaxpayerActivity.objects.filter(company__isnull=True)
    
    for activity in activities_without_company:
        # Try to find a company that might match (if any)
        # For now, we'll just delete orphaned activities since they need company context
        activity.delete()


def migrate_activity_data_backward(apps, schema_editor):
    """Nothing to do on reverse - activities will remain linked to companies"""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0001_initial'),
        ('taxpayers', '0004_link_taxpayer_models_to_company'),
    ]

    operations = [
        # Step 1: Add company field (nullable initially)
        migrations.AddField(
            model_name='taxpayeractivity',
            name='company',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='taxpayer_activities',
                to='companies.company',
                help_text='Empresa asociada'
            ),
        ),
        
        # Step 2: Migrate existing data
        migrations.RunPython(migrate_activity_data_forward, migrate_activity_data_backward),
        
        # Step 3: Remove the unique constraint on code alone
        migrations.AlterField(
            model_name='taxpayeractivity',
            name='code',
            field=models.CharField(max_length=10),
        ),
        
        # Step 4: Make company field required
        migrations.AlterField(
            model_name='taxpayeractivity',
            name='company',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='taxpayer_activities',
                to='companies.company',
                help_text='Empresa asociada'
            ),
        ),
        
        # Step 5: Add unique constraint on company+code combination
        migrations.AlterUniqueTogether(
            name='taxpayeractivity',
            unique_together={('company', 'code')},
        ),
        
        # Step 6: Update Meta ordering
        migrations.AlterModelOptions(
            name='taxpayeractivity',
            options={
                'ordering': ['company', 'code'],
                'verbose_name': 'Taxpayer Activity',
                'verbose_name_plural': 'Taxpayer Activities'
            },
        ),
    ]