"""Rebuild every stored face encoding from the photo already on disk.

`face_utils` now aligns faces with the 68-point landmark model. Encodings built
with the old 5-point default were aligned differently, so distances measured
against them drift and students look less like themselves than they are. The
original photo is kept in `StudentProfile.face_image`, so the fix is a re-encode
rather than asking everyone to register again.

Safe to re-run: it simply overwrites each encoding with a fresh one.
"""
from django.core.management.base import BaseCommand

from apps.accounts.face_utils import FaceError, encode_face
from apps.accounts.models import StudentProfile


class Command(BaseCommand):
    help = "Recompute every StudentProfile.face_encoding from its stored photo."

    def add_arguments(self, parser):
        parser.add_argument(
            "--matric",
            help="Re-encode only this matric number instead of every profile.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would change without writing anything.",
        )

    def handle(self, *args, **opts):
        profiles = StudentProfile.objects.select_related("user").order_by("matric_number")
        if opts["matric"]:
            profiles = profiles.filter(matric_number=opts["matric"])

        done = skipped = 0
        for profile in profiles:
            label = f"{profile.matric_number} ({profile.user.username})"
            if not profile.face_image:
                self.stderr.write(self.style.WARNING(f"{label}: no photo on file, skipped"))
                skipped += 1
                continue
            try:
                with profile.face_image.open("rb") as fh:
                    encoding = encode_face(fh.read())
            except FileNotFoundError:
                self.stderr.write(
                    self.style.WARNING(f"{label}: photo missing from disk, skipped")
                )
                skipped += 1
                continue
            except FaceError as exc:
                # Left alone rather than blanked: the old encoding still works
                # well enough to sign in with, and losing it locks the student out.
                self.stderr.write(self.style.WARNING(f"{label}: {exc} — left unchanged"))
                skipped += 1
                continue

            if not opts["dry_run"]:
                profile.face_encoding = encoding
                profile.save(update_fields=("face_encoding",))
            done += 1
            self.stdout.write(f"{label}: re-encoded")

        verb = "would re-encode" if opts["dry_run"] else "re-encoded"
        self.stdout.write(self.style.SUCCESS(f"{verb} {done} profile(s), {skipped} skipped"))
