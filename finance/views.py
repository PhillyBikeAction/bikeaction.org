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

    def get_initial(self):
        user = self.request.user
        discord = user.profile.discord
        return {
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "discord_handle": discord.extra_data.get("username") if discord else "",
        }

    def form_valid(self, form):
        form.save()
        messages.add_message(
            self.request,
            messages.INFO,
            "Reimbursement request submitted!",
        )
        return HttpResponseRedirect(reverse("profile"))

