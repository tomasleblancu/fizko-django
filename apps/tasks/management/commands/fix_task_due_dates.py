"""
Django management command to fix missing due dates for existing tasks
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from apps.tasks.models import Process, ProcessTask, Task


class Command(BaseCommand):
    help = 'Fix missing due dates for existing tasks based on their process configuration'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Only show what would be updated without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)

        if dry_run:
            self.stdout.write(self.style.WARNING('Running in DRY RUN mode - no changes will be made'))

        # Get all tasks without due dates
        tasks_without_due_date = Task.objects.filter(due_date__isnull=True)
        self.stdout.write(f"Found {tasks_without_due_date.count()} tasks without due dates")

        updated_count = 0
        errors = []

        for task in tasks_without_due_date:
            try:
                # Find the ProcessTask that contains this task
                process_task = ProcessTask.objects.filter(task=task).first()

                if not process_task:
                    continue

                process = process_task.process

                # Calculate due date based on process configuration
                task_due_date = None

                if process_task.due_date_offset_days is not None:
                    offset_days = process_task.due_date_offset_days

                    if offset_days > 0:
                        # Positive offset: calculate from process start date or now
                        base_date = process.start_date or timezone.now()
                        task_due_date = base_date + timedelta(days=offset_days)
                    else:
                        # Negative offset: calculate from process due date
                        if process.due_date:
                            task_due_date = process.due_date + timedelta(days=offset_days)

                elif process_task.due_date_from_previous:
                    # For now, use process due date for tasks that depend on previous
                    task_due_date = process.due_date

                else:
                    # Default: use process due date
                    task_due_date = process.due_date

                if task_due_date:
                    if dry_run:
                        self.stdout.write(f"Would update task '{task.title}' with due date: {task_due_date}")
                    else:
                        task.due_date = task_due_date
                        task.save()
                        self.stdout.write(f"✅ Updated task '{task.title}' with due date: {task_due_date}")

                    updated_count += 1

            except Exception as e:
                error_msg = f"Error updating task {task.id} ({task.title}): {str(e)}"
                errors.append(error_msg)
                self.stdout.write(self.style.ERROR(error_msg))

        # Summary
        self.stdout.write(f"\n📊 Summary:")
        if dry_run:
            self.stdout.write(f"  - Tasks that would be updated: {updated_count}")
        else:
            self.stdout.write(f"  - Tasks updated: {updated_count}")

        if errors:
            self.stdout.write(self.style.ERROR(f"  - Errors: {len(errors)}"))
            for error in errors:
                self.stdout.write(self.style.ERROR(f"    {error}"))

        if not dry_run and updated_count > 0:
            self.stdout.write(self.style.SUCCESS(f"\n✅ Successfully updated {updated_count} task due dates"))