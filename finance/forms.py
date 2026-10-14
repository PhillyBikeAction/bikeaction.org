from django import forms

from finance.models import Reimbursement


class ReimbursementForm(forms.ModelForm):
    class Meta:
        model = Reimbursement
        fields = [
            "first_name",
            "last_name",
            "email",
            "discord_handle",
            "vendor_name",
            "amount",
            "expense_date",
            "explanation",
            "expense_support",
            "reimbursement_method",
            "payment_contact",
        ]

    first_name = forms.CharField(required=True)
    last_name = forms.CharField(required=True)
    email = forms.EmailField(required=True, max_length=100)
    discord_handle = forms.CharField(
        required=False,
        help_text="Only required if you are in the PBA Discord.",
    )
    vendor_name = forms.CharField(required=True)
    amount = forms.DecimalField(
        required=True,
        help_text="Expenses of $60 or more require approval by the PBA Board.",
    )
    expense_date = forms.DateField(required=True)
    explanation = forms.CharField(
        required=True,
        widget=forms.Textarea,
        max_length=250,
        help_text=(
            "Brief explanation of the expense. "
            "If it is related to a specific project, please name the project."
        ),
    )
    expense_support = forms.FileField(
        required=True,
        help_text="Attach any relevant invoices, receipts, etc. here.",
    )
    reimbursement_method = forms.ChoiceField(
        choices=[("zelle", "Zelle"), ("paypal", "PayPal")],
        help_text=(
            "If you would like to be reimbursed via check, please email finance@bikeaction.org "
            "or message Brian (briandelmore) on Discord to arrange payment."
        ),
    )
    payment_contact = forms.CharField(
        help_text=(
            "What is the email address or phone number associated with Zelle or PayPal account?"
        ),
    )
