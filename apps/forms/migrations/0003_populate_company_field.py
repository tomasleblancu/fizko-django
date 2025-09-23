# Data migration to populate company field in TaxForm
from django.db import migrations
from django.db.models import Q


def populate_company_field(apps, schema_editor):
    """
    Poblar el campo company basado en company_rut
    """
    TaxForm = apps.get_model('forms', 'TaxForm')
    Company = apps.get_model('companies', 'Company')

    # Obtener todos los TaxForm que no tienen company asignado
    forms_without_company = TaxForm.objects.filter(company__isnull=True)

    updated_count = 0
    missing_companies = set()

    for tax_form in forms_without_company:
        # Buscar company por tax_id (formato completo con dígito verificador)
        full_rut = f"{tax_form.company_rut}-{tax_form.company_dv}"

        try:
            company = Company.objects.get(
                Q(tax_id=full_rut) |
                Q(tax_id=f"{tax_form.company_rut.replace('.', '')}-{tax_form.company_dv}")
            )
            tax_form.company = company
            tax_form.save()
            updated_count += 1
        except Company.DoesNotExist:
            missing_companies.add(full_rut)
        except Company.MultipleObjectsReturned:
            # En caso de múltiples, tomar el primero
            company = Company.objects.filter(
                Q(tax_id=full_rut) |
                Q(tax_id=f"{tax_form.company_rut.replace('.', '')}-{tax_form.company_dv}")
            ).first()
            tax_form.company = company
            tax_form.save()
            updated_count += 1

    print(f"✅ Actualizados {updated_count} formularios con company")
    if missing_companies:
        print(f"⚠️ No se encontraron companies para: {missing_companies}")


def reverse_populate_company_field(apps, schema_editor):
    """
    Reversa: limpiar el campo company
    """
    TaxForm = apps.get_model('forms', 'TaxForm')
    TaxForm.objects.update(company=None)


class Migration(migrations.Migration):

    dependencies = [
        ('forms', '0002_alter_taxform_unique_together_taxform_company_and_more'),
        ('companies', '0004_remove_taxpayer_field'),
    ]

    operations = [
        migrations.RunPython(
            populate_company_field,
            reverse_populate_company_field,
        ),
    ]