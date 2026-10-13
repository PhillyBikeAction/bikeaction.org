from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.views.generic import CreateView
from django.http import HttpResponseRedirect

from finance.forms import ReimbursementForm
from finance.models import Reimbursement


class ReimbursementCreateView(LoginRequiredMixin, CreateView):
    model = Reimbursement
    form_class = ReimbursementForm
    template_name = "reimbursement.html"

    def form_valid(self, form):
        messages.add_message(
            self.request,
            messages.INFO,
            "Reimbursement request submitted!",
        )
        return HttpResponseRedirect(reverse("profile"))

