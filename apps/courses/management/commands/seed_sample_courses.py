from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.courses.models import Course


SAMPLES = [
    ("CSC101", "Introduction to Computing", 3, "Computer Science"),
    ("MTH101", "Elementary Mathematics I", 3, "Mathematics"),
    ("ENG101", "Use of English", 2, "General Studies"),
    ("PHY101", "General Physics I", 3, "Physics"),
    ("GST101", "Communication Skills", 2, "General Studies"),
]


class Command(BaseCommand):
    help = "Seed default sample courses. Idempotent on Course.code."

    def add_arguments(self, parser):
        parser.add_argument(
            "--lecturer",
            help="Username of the lecturer to own seeded courses.",
        )

    def handle(self, *args, **opts):
        User = get_user_model()
        lecturers = User.objects.filter(role="lecturer")
        username = opts.get("lecturer")
        if username:
            try:
                lecturer = lecturers.get(username=username)
            except User.DoesNotExist:
                raise CommandError(f"No lecturer user named {username!r}.")
        else:
            count = lecturers.count()
            if count == 0:
                raise CommandError(
                    "No lecturer users exist. Create one first or pass --lecturer."
                )
            if count > 1:
                raise CommandError(
                    "Multiple lecturers exist; pass --lecturer <username>."
                )
            lecturer = lecturers.first()

        created = skipped = 0
        for code, title, unit, dept in SAMPLES:
            if Course.objects.filter(code=code).exists():
                self.stdout.write(f"  skip   {code} (exists)")
                skipped += 1
                continue
            Course.objects.create(
                code=code, title=title, unit=unit, department=dept, lecturer=lecturer
            )
            self.stdout.write(
                self.style.SUCCESS(f"  create {code} -> {lecturer.username}")
            )
            created += 1
        self.stdout.write(
            self.style.SUCCESS(f"Done. created={created} skipped={skipped}")
        )
