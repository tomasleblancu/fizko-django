# Migration to reverse TaxPayer-Company relationship for proper CASCADE deletion

from django.db import migrations, models
import django.db.models.deletion


def migrate_relationship_forward(apps, schema_editor):
    """Migrate the relationship from Company.taxpayer -> TaxPayer.company"""
    Company = apps.get_model('companies', 'Company')
    TaxPayer = apps.get_model('taxpayers', 'TaxPayer')
    
    # Update existing TaxPayers to point to their companies
    companies_with_taxpayers = Company.objects.select_related('taxpayer').filter(taxpayer__isnull=False)
    
    for company in companies_with_taxpayers:
        if company.taxpayer:
            # Set the company field in the taxpayer
            company.taxpayer.company = company
            company.taxpayer.save()


def migrate_relationship_backward(apps, schema_editor):
    """Reverse migration - recreate Company.taxpayer field and populate it"""
    Company = apps.get_model('companies', 'Company')
    TaxPayer = apps.get_model('taxpayers', 'TaxPayer')
    
    # For each TaxPayer that has a company, set the company's taxpayer field
    taxpayers_with_companies = TaxPayer.objects.select_related('company').filter(company__isnull=False)
    
    for taxpayer in taxpayers_with_companies:
        if taxpayer.company:
            taxpayer.company.taxpayer = taxpayer
            taxpayer.company.save()


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0001_initial'),
        ('taxpayers', '0005_link_taxpayeractivity_to_company'),
    ]

    operations = [
        # Step 1: Add company field to TaxPayer (nullable initially)
        migrations.AddField(
            model_name='taxpayer',
            name='company',
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='taxpayer',
                to='companies.company',
                help_text='Empresa a la que pertenece este contribuyente'
            ),
        ),
        
        # Step 2: Migrate data from Company.taxpayer to TaxPayer.company
        migrations.RunPython(migrate_relationship_forward, migrate_relationship_backward),
        
        # Step 3: Make company field required in TaxPayer
        migrations.AlterField(
            model_name='taxpayer',
            name='company',
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='taxpayer',
                to='companies.company',
                help_text='Empresa a la que pertenece este contribuyente'
            ),
        ),
    ]