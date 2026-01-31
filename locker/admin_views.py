from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import redirect, render
from django.utils import timezone

from .admin_forms import CheckoutForm, LoanFormSet, ReturnForm
from .models import Item, Loan


@login_required
@permission_required("locker.view_item", raise_exception=True)
def checkout_items(request):
    items = Item.objects.filter(available_quantity__gt=0)
    if request.method == "POST":
        checkout_form = CheckoutForm(request.POST)
        formset = LoanFormSet(request.POST)
        if formset.is_valid() and checkout_form.is_valid():
            expected_return = checkout_form.cleaned_data["expected_return"]
            checkout_note = checkout_form.cleaned_data["note"]
            count = 0
            for form in formset.cleaned_data:
                item = Item.objects.get(id=form["item_id"])
                if (
                    form["quantity"]
                    and form["quantity"] > 0
                    and form["quantity"] <= item.available_quantity
                ):
                    count += 1
                    Loan.objects.create(
                        item=item,
                        user=request.user,
                        quantity=form["quantity"],
                        expected_return=expected_return,
                        checkout_note=checkout_note,
                    )

                    item.available_quantity -= form["quantity"]
                    item.save()
            messages.success(request, f"Successfully borrowed {count} item(s)!")
            return redirect("organizer_admin:locker_loan_changelist")
        else:
            messages.error(request, "Invalid form")
            return redirect("organizer_admin:locker_loan_changelist")
    else:
        initial_data = [
            {
                "item_id": item.id,
                "name": item.name,
                "type": item.type.name,
                "available_quantity": item.available_quantity,
            }
            for item in items
        ]
        formset = LoanFormSet(initial=initial_data)
        initial_due_date = timezone.now() + timedelta(days=7)
        checkout_form = CheckoutForm(initial={"expected_return": initial_due_date})

    return render(request, "checkout.html", {"formset": formset, "checkout_form": checkout_form})


@login_required
@permission_required("locker.view_item", raise_exception=True)
def return_items(request):

    active_loans = Loan.objects.filter(
        user=request.user,
        active=True,
    )

    if request.method == "POST":
        form = ReturnForm(request.POST, user_loans=active_loans)
        if form.is_valid():
            selected_loans = form.cleaned_data["loans"]
            return_note = form.cleaned_data["return_note"]

            if not selected_loans:
                messages.error(request, "Please select at least one item to return.")
                return redirect("return_items")

            for loan in selected_loans:
                loan.active = False
                loan.returned_at = timezone.now()
                loan.return_note = return_note
                loan.save()

                item = loan.item
                item.available_quantity += loan.quantity
                item.save()

            messages.success(request, f"Successfully returned {len(selected_loans)} item(s)!")
            return redirect("organizer_admin:locker_loan_changelist")
    else:
        form = ReturnForm(user_loans=active_loans)

    return render(
        request,
        "return.html",
        {
            "form": form,
            "active_loans": active_loans,
        },
    )
