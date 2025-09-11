# Generated migration for linking TaxPayer models to Company

from django.db import migrations, models
import django.db.models.deletion


def migrate_data_forward(apps, schema_editor):
    """Migrate existing data from rut/dv to company relationships"""
    Company = apps.get_model('companies', 'Company')
    TaxpayerAddress = apps.get_model('taxpayers', 'TaxpayerAddress')
    TaxpayerPartner = apps.get_model('taxpayers', 'TaxpayerPartner')
    TaxpayerRepresentative = apps.get_model('taxpayers', 'TaxpayerRepresentative')
    TaxpayerStamp = apps.get_model('taxpayers', 'TaxpayerStamp')
    
    # Migrate TaxpayerAddress
    for address in TaxpayerAddress.objects.all():
        if hasattr(address, 'taxpayer_rut') and address.taxpayer_rut:
            tax_id = f"{address.taxpayer_rut}-{address.taxpayer_dv}"
            try:
                company = Company.objects.get(tax_id=tax_id)
                address.company = company
                address.save()
            except Company.DoesNotExist:
                pass  # Skip if no matching company found
    
    # Migrate TaxpayerPartner
    for partner in TaxpayerPartner.objects.all():
        if hasattr(partner, 'company_rut') and partner.company_rut:
            tax_id = f"{partner.company_rut}-{partner.company_dv}"
            try:
                company = Company.objects.get(tax_id=tax_id)
                partner.company = company
                partner.save()
            except Company.DoesNotExist:
                pass
    
    # Migrate TaxpayerRepresentative
    for representative in TaxpayerRepresentative.objects.all():
        if hasattr(representative, 'company_rut') and representative.company_rut:
            tax_id = f"{representative.company_rut}-{representative.company_dv}"
            try:
                company = Company.objects.get(tax_id=tax_id)
                representative.company = company
                representative.save()
            except Company.DoesNotExist:
                pass
    
    # Migrate TaxpayerStamp
    for stamp in TaxpayerStamp.objects.all():
        if hasattr(stamp, 'company_rut') and stamp.company_rut:
            tax_id = f"{stamp.company_rut}-{stamp.company_dv}"
            try:
                company = Company.objects.get(tax_id=tax_id)
                stamp.company = company
                stamp.save()
            except Company.DoesNotExist:
                pass


def migrate_data_backward(apps, schema_editor):
    """Migrate data back from company to rut/dv fields"""
    TaxpayerAddress = apps.get_model('taxpayers', 'TaxpayerAddress')
    TaxpayerPartner = apps.get_model('taxpayers', 'TaxpayerPartner')
    TaxpayerRepresentative = apps.get_model('taxpayers', 'TaxpayerRepresentative')
    TaxpayerStamp = apps.get_model('taxpayers', 'TaxpayerStamp')
    
    # Reverse migrate TaxpayerAddress
    for address in TaxpayerAddress.objects.all():
        if address.company and address.company.tax_id:
            rut, dv = address.company.tax_id.split('-')
            address.taxpayer_rut = rut
            address.taxpayer_dv = dv.upper()
            address.save()
    
    # Reverse migrate TaxpayerPartner
    for partner in TaxpayerPartner.objects.all():
        if partner.company and partner.company.tax_id:
            rut, dv = partner.company.tax_id.split('-')
            partner.company_rut = rut
            partner.company_dv = dv.upper()
            partner.save()
    
    # Reverse migrate TaxpayerRepresentative
    for representative in TaxpayerRepresentative.objects.all():
        if representative.company and representative.company.tax_id:
            rut, dv = representative.company.tax_id.split('-')
            representative.company_rut = rut
            representative.company_dv = dv.upper()
            representative.save()
    
    # Reverse migrate TaxpayerStamp
    for stamp in TaxpayerStamp.objects.all():
        if stamp.company and stamp.company.tax_id:
            rut, dv = stamp.company.tax_id.split('-')
            stamp.company_rut = rut
            stamp.company_dv = dv.upper()
            stamp.save()


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0001_initial'),
        ('taxpayers', '0003_add_taxpayer_sii_credentials'),
    ]

    operations = [
        # Step 1: Add new company field (nullable initially)
        migrations.AddField(
            model_name='taxpayeraddress',
            name='company',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='taxpayer_addresses',
                to='companies.company',
                help_text='Empresa asociada'
            ),
        ),
        migrations.AddField(
            model_name='taxpayerpartner',
            name='company',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='taxpayer_partners',
                to='companies.company',
                help_text='Empresa asociada'
            ),
        ),
        migrations.AddField(
            model_name='taxpayerrepresentative',
            name='company',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='taxpayer_representatives',
                to='companies.company',
                help_text='Empresa asociada'
            ),
        ),
        migrations.AddField(
            model_name='taxpayerstamp',
            name='company',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='taxpayer_stamps',
                to='companies.company',
                help_text='Empresa asociada'
            ),
        ),
        
        # Step 2: Migrate data from rut/dv to company
        migrations.RunPython(migrate_data_forward, migrate_data_backward),
        
        # Step 3: Remove old rut/dv fields
        migrations.RemoveField(
            model_name='taxpayeraddress',
            name='taxpayer_rut',
        ),
        migrations.RemoveField(
            model_name='taxpayeraddress',
            name='taxpayer_dv',
        ),
        migrations.RemoveField(
            model_name='taxpayerpartner',
            name='company_rut',
        ),
        migrations.RemoveField(
            model_name='taxpayerpartner',
            name='company_dv',
        ),
        migrations.RemoveField(
            model_name='taxpayerrepresentative',
            name='company_rut',
        ),
        migrations.RemoveField(
            model_name='taxpayerrepresentative',
            name='company_dv',
        ),
        migrations.RemoveField(
            model_name='taxpayerstamp',
            name='company_rut',
        ),
        migrations.RemoveField(
            model_name='taxpayerstamp',
            name='company_dv',
        ),
        
        # Step 4: Make company field required (remove null=True)
        migrations.AlterField(
            model_name='taxpayeraddress',
            name='company',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='taxpayer_addresses',
                to='companies.company',
                help_text='Empresa asociada'
            ),
        ),
        migrations.AlterField(
            model_name='taxpayerpartner',
            name='company',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='taxpayer_partners',
                to='companies.company',
                help_text='Empresa asociada'
            ),
        ),
        migrations.AlterField(
            model_name='taxpayerrepresentative',
            name='company',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='taxpayer_representatives',
                to='companies.company',
                help_text='Empresa asociada'
            ),
        ),
        migrations.AlterField(
            model_name='taxpayerstamp',
            name='company',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='taxpayer_stamps',
                to='companies.company',
                help_text='Empresa asociada'
            ),
        ),
    ]