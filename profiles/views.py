from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views.generic import CreateView, DeleteView, DetailView, UpdateView
from djstripe.models import Customer

from profiles.forms import NewsletterSignupForm, ProfileUpdateForm
from profiles.models import NewsletterSignup, Profile, ShirtInterest


class ProfileDetailView(LoginRequiredMixin, DetailView):
    model = Profile

    def get_object(self, queryset=None):
        return self.request.user.profile


class ProfileDonationsPartial(LoginRequiredMixin, DetailView):
    model = Profile
    template_name = "profiles/_donations_partial.html"

    def get_object(self, queryset=None):
        try:
            customer = Customer.objects.filter(subscriber=self.request.user).first()
            if customer:
                customer.api_retrieve()
                customer._sync_subscriptions()
                customer._sync_charges()
        except Exception:
            pass
        return self.request.user.profile


class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    model = Profile
    form_class = ProfileUpdateForm

    def get_success_url(self):
        return reverse("profile")

    def get_object(self):
        return Profile.objects.get(user=self.request.user)


class NewsletterSignupView(CreateView):
    model = NewsletterSignup
    form_class = NewsletterSignupForm

    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.save()
        messages.add_message(self.request, messages.INFO, "Newsletter signup received!")
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse("index")


class ShirtInterestView(LoginRequiredMixin, CreateView):
    model = ShirtInterest
    fields = ["fit", "print_color", "size"]

    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.user = self.request.user
        obj.save()
        messages.add_message(self.request, messages.INFO, "T-Shirt interest recorded!")
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse("profile")


class ShirtInterestDeleteView(LoginRequiredMixin, DeleteView):
    model = ShirtInterest

    def get_success_url(self):
        messages.add_message(self.request, messages.INFO, "T-Shirt interest deleted.")
        return reverse("profile")
