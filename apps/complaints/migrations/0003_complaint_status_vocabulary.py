from django.db import migrations, models


def to_four_value_status(apps, schema_editor):
    """`submitted` becomes `unreviewed`; anything already with the VC becomes
    `escalated`.

    Order matters: the rename runs first so the second pass can key off
    `escalated_at` alone. A complaint the HOD already resolved keeps `resolved`
    — it is the further-along state, and `escalated_at`, which is what the VC
    console actually filters on, is untouched either way.
    """
    Complaint = apps.get_model("complaints", "Complaint")
    Complaint.objects.filter(status="submitted").update(status="unreviewed")
    Complaint.objects.filter(escalated_at__isnull=False).exclude(
        status="resolved"
    ).update(status="escalated")


def back_to_three_value_status(apps, schema_editor):
    """`escalated` has no three-value equivalent, so it collapses back to
    `submitted` alongside the renamed rows. Nothing is lost that the VC console
    reads: `escalated_at` still marks every one of them.
    """
    Complaint = apps.get_model("complaints", "Complaint")
    Complaint.objects.filter(status__in=("unreviewed", "escalated")).update(
        status="submitted"
    )


class Migration(migrations.Migration):

    dependencies = [
        ("complaints", "0002_complaint_escalation"),
    ]

    operations = [
        migrations.AlterField(
            model_name="complaint",
            name="status",
            # Literals rather than `Complaint.Status.UNREVIEWED`: a migration
            # that imports the live enum breaks the day the enum is renamed
            # again, which is the exact thing this migration exists to do.
            field=models.CharField(
                choices=[
                    ("unreviewed", "Unreviewed"),
                    ("reviewed", "Reviewed"),
                    ("escalated", "Escalated"),
                    ("resolved", "Resolved"),
                ],
                default="unreviewed",
                max_length=16,
            ),
        ),
        migrations.RunPython(to_four_value_status, back_to_three_value_status),
    ]
