from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.urls import reverse
from django.views.generic import CreateView
from django.http import HttpResponseRedirect

from finance.forms import MAX_EXPENSE_SUPPORT_FILES, ReimbursementForm
from finance.models import Reimbursement, ReimbursementSupportingMaterial


class ReimbursementCreateView(LoginRequiredMixin, CreateView):
    model = Reimbursement
    form_class = ReimbursementForm
    template_name = "reimbursement.html"

    def get_initial(self):
        user = self.request.user
        discord = user.profile.discord
        return {
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "discord_handle": discord.extra_data.get("username") if discord else "",
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["max_expense_support_files"] = MAX_EXPENSE_SUPPORT_FILES
        return context

    def form_valid(self, form):
        with transaction.atomic():
            reimbursement = form.save()
            ReimbursementSupportingMaterial.objects.bulk_create(
                ReimbursementSupportingMaterial(application=reimbursement, file=file)
                for file in form.cleaned_data["expense_support"]
            )
        messages.add_message(
            self.request,
            messages.INFO,
            "Reimbursement request submitted!",
        )
        return HttpResponseRedirect(reverse("profile"))

