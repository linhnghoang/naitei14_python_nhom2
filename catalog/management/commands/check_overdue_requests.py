from django.core.management.base import BaseCommand
from django.utils import timezone
from catalog.models import BorrowRequest


class Command(BaseCommand):
    help = "Check for overdue borrow requests and update their status"

    def handle(self, *args, **options):
        today = timezone.now().date()
        # Find approved requests where requested_to (due date) is in the past
        overdue_requests = BorrowRequest.objects.filter(
            status=BorrowRequest.Status.APPROVED, requested_to__lt=today
        )

        count = 0
        for req in overdue_requests:
            req.status = BorrowRequest.Status.OVERDUE
            req.save()
            count += 1

        self.stdout.write(
            self.style.SUCCESS(f"Successfully updated {count} overdue requests.")
        )
