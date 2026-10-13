from django.urls import path

from finance import views

urlpatterns = [
    path("", views.ReimbursementCreateView.as_view(), name="reimbusement_submission"),
]
