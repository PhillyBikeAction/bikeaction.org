from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("finance", "0001_initial"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="reimbursement",
            name="expense_support",
        ),
    ]
