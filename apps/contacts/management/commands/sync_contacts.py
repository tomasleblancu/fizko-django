"""
Django management command to synchronize contacts based on document issuers and recipients.
Creates or updates contacts based on RUTs found in the documents app.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from django.core.exceptions import ValidationError
import logging

from apps.contacts.models import Contact
from apps.documents.models import Document
from apps.companies.models import Company

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Synchronize contacts based on document issuers and recipients'

    def add_arguments(self, parser):
        parser.add_argument(
            '--company-id',
            type=int,
            help='Sync contacts for a specific company only'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview changes without actually creating/updating contacts'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Enable verbose output'
        )

    def handle(self, *args, **options):
        self.dry_run = options['dry_run']
        self.verbose = options['verbose']
        company_id = options.get('company_id')

        # Initialize counters
        self.stats = {
            'processed_companies': 0,
            'processed_documents': 0,
            'created_contacts': 0,
            'updated_contacts': 0,
            'errors': 0,
        }

        if self.dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE - No changes will be saved to database")
            )

        # Get companies to process
        if company_id:
            try:
                companies = [Company.objects.get(id=company_id)]
                self.stdout.write(f"Processing specific company: {companies[0].name}")
            except Company.DoesNotExist:
                raise CommandError(f"Company with ID {company_id} does not exist")
        else:
            companies = Company.objects.filter(is_active=True)
            self.stdout.write(f"Processing {companies.count()} active companies")

        # Process each company
        for company in companies:
            self.sync_company_contacts(company)

        # Print final stats
        self.print_final_stats()

    def sync_company_contacts(self, company):
        """Sync contacts for a specific company"""
        if self.verbose:
            self.stdout.write(f"\n--- Processing company: {company.name} (ID: {company.id}) ---")

        # Get all documents for this company
        documents = Document.objects.filter(company=company)
        document_count = documents.count()

        if document_count == 0:
            if self.verbose:
                self.stdout.write(f"No documents found for company {company.name}")
            return

        if self.verbose:
            self.stdout.write(f"Found {document_count} documents to analyze")

        # Track unique RUTs we encounter
        rut_data = {}

        # Process each document to collect RUT data
        for doc in documents:
            self.stats['processed_documents'] += 1

            # Process issuer (could be a provider if this is a received document)
            issuer_rut = self.format_rut(doc.issuer_company_rut, doc.issuer_company_dv)
            if issuer_rut and issuer_rut != company.tax_id:
                if issuer_rut not in rut_data:
                    rut_data[issuer_rut] = {
                        'name': doc.issuer_name,
                        'address': doc.issuer_address,
                        'is_client': False,
                        'is_provider': False,
                    }

                # If this document is received by the company, issuer is a provider
                if doc.is_received_by_company:
                    rut_data[issuer_rut]['is_provider'] = True
                # If this document is issued by another company to us, they might be a client
                elif doc.is_issued_by_company:
                    rut_data[issuer_rut]['is_client'] = True

            # Process recipient (could be a client if this is an issued document)
            recipient_rut = self.format_rut(doc.recipient_rut, doc.recipient_dv)
            if recipient_rut and recipient_rut != company.tax_id:
                if recipient_rut not in rut_data:
                    rut_data[recipient_rut] = {
                        'name': doc.recipient_name,
                        'address': doc.recipient_address,
                        'is_client': False,
                        'is_provider': False,
                    }

                # If this document is issued by the company, recipient is a client
                if doc.is_issued_by_company:
                    rut_data[recipient_rut]['is_client'] = True
                # If this document is received by the company from the recipient, they are a provider
                elif doc.is_received_by_company:
                    rut_data[recipient_rut]['is_provider'] = True

        if self.verbose:
            self.stdout.write(f"Found {len(rut_data)} unique RUTs to process")

        # Now create or update contacts for each unique RUT
        for rut, data in rut_data.items():
            self.create_or_update_contact(company, rut, data)

        self.stats['processed_companies'] += 1

    def create_or_update_contact(self, company, rut, data):
        """Create or update a contact for the given company and RUT"""
        try:
            # Try to get existing contact
            existing_contact = Contact.objects.filter(
                company=company,
                tax_id=rut
            ).first()

            if existing_contact:
                # Update existing contact
                updated = False

                # Update name if we have a better one (longer or if current is empty)
                if data['name'] and (not existing_contact.name or len(data['name']) > len(existing_contact.name)):
                    existing_contact.name = data['name']
                    updated = True

                # Update address if current is empty
                if data['address'] and not existing_contact.address:
                    existing_contact.address = data['address']
                    updated = True

                # Update roles (additive - don't remove existing roles)
                if data['is_client'] and not existing_contact.is_client:
                    existing_contact.is_client = True
                    updated = True

                if data['is_provider'] and not existing_contact.is_provider:
                    existing_contact.is_provider = True
                    updated = True

                if updated and not self.dry_run:
                    existing_contact.save()

                if updated:
                    self.stats['updated_contacts'] += 1
                    if self.verbose:
                        roles = []
                        if existing_contact.is_client:
                            roles.append('client')
                        if existing_contact.is_provider:
                            roles.append('provider')
                        self.stdout.write(
                            f"  Updated contact: {rut} - {existing_contact.name} "
                            f"[{', '.join(roles)}]"
                        )
            else:
                # Create new contact
                # Ensure at least one role is set
                if not data['is_client'] and not data['is_provider']:
                    data['is_provider'] = True  # Default to provider if unclear

                if not self.dry_run:
                    contact = Contact.objects.create(
                        company=company,
                        tax_id=rut,
                        name=data['name'] or '',
                        address=data['address'] or '',
                        is_client=data['is_client'],
                        is_provider=data['is_provider'],
                        is_active=True
                    )

                self.stats['created_contacts'] += 1
                if self.verbose:
                    roles = []
                    if data['is_client']:
                        roles.append('client')
                    if data['is_provider']:
                        roles.append('provider')
                    self.stdout.write(
                        f"  Created contact: {rut} - {data['name']} "
                        f"[{', '.join(roles)}]"
                    )

        except ValidationError as e:
            self.stats['errors'] += 1
            self.stdout.write(
                self.style.ERROR(f"Validation error for RUT {rut}: {e}")
            )
        except Exception as e:
            self.stats['errors'] += 1
            self.stdout.write(
                self.style.ERROR(f"Error processing RUT {rut}: {str(e)}")
            )

    def format_rut(self, rut_number, dv):
        """Format RUT with proper Chilean format XX.XXX.XXX-X"""
        if not rut_number or not dv:
            return None

        # Clean the RUT number
        clean_rut = str(rut_number).replace('.', '').replace('-', '')

        # Format with dots
        if len(clean_rut) >= 7:
            formatted = f"{clean_rut[:-6]}.{clean_rut[-6:-3]}.{clean_rut[-3:]}-{dv.upper()}"
        elif len(clean_rut) >= 4:
            formatted = f"{clean_rut[:-3]}.{clean_rut[-3:]}-{dv.upper()}"
        else:
            formatted = f"{clean_rut}-{dv.upper()}"

        return formatted

    def print_final_stats(self):
        """Print final synchronization statistics"""
        self.stdout.write("\n" + "="*50)
        self.stdout.write(self.style.SUCCESS("SYNCHRONIZATION COMPLETE"))
        self.stdout.write("="*50)

        self.stdout.write(f"Companies processed: {self.stats['processed_companies']}")
        self.stdout.write(f"Documents analyzed: {self.stats['processed_documents']}")
        self.stdout.write(f"Contacts created: {self.stats['created_contacts']}")
        self.stdout.write(f"Contacts updated: {self.stats['updated_contacts']}")

        if self.stats['errors'] > 0:
            self.stdout.write(
                self.style.ERROR(f"Errors encountered: {self.stats['errors']}")
            )

        total_changes = self.stats['created_contacts'] + self.stats['updated_contacts']
        if total_changes > 0:
            self.stdout.write(
                self.style.SUCCESS(f"Total contacts affected: {total_changes}")
            )

        if self.dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN - No changes were actually saved")
            )