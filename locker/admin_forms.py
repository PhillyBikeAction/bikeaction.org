from django import forms
from django.forms import formset_factory

from .models import Item, Loan


class LoanForm(forms.Form):
    item_id = forms.IntegerField(widget=forms.HiddenInput(), required=False)
    name = forms.CharField(disabled=True, required=False)
    type = forms.CharField(disabled=True, required=False)
    available_quantity = forms.IntegerField(disabled=True, required=False)
    quantity = forms.IntegerField(min_value=0, required=False, label="Withdraw")

    def clean_quantity(self):
        item_id = self.cleaned_data.get("item_id")
        item = Item.objects.get(id=item_id)
        quantity = self.cleaned_data.get("quantity") or 0
        if quantity > item.available_quantity:
            raise forms.ValidationError("Not enough stock available.")
        return quantity


LoanFormSet = formset_factory(LoanForm, extra=0)


class CheckoutForm(forms.Form):
    note = forms.CharField(
        label="Checkout Note",
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Add any notes about the loan (optional)",
        required=False,
    )
    expected_return = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={"type": "datetime-local", "class": "form-control"})
    )


class ReturnForm(forms.Form):
    loans = forms.ModelMultipleChoiceField(
        queryset=Loan.objects.none(), widget=forms.CheckboxSelectMultiple, required=False
    )
    return_note = forms.CharField(
        label="Return Note",
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Add any notes about the return (optional)",
        required=False,
    )

    def __init__(self, *args, user_loans=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user_loans is not None:
            self.fields["loans"].queryset = user_loans
