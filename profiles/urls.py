from django.urls import path

from profiles import views

urlpatterns = [
    path("", views.ProfileDetailView.as_view(), name="profile"),
    path(
        "_partials/donations/",
        views.ProfileDonationsPartial.as_view(),
        name="profile_donations_partial",
    ),
    path(
        "_partials/rcos/",
        views.ProfileDistrictAndRCOPartial.as_view(),
        name="profile_rcos_partial",
    ),
    path("edit/", views.ProfileUpdateView.as_view(), name="profile_update"),
    path("tshirt/", views.ShirtOrderView.as_view(), name="shirt_order"),
    path("tshirt/<pk>/delete/", views.ShirtOrderDeleteView.as_view(), name="shirt_delete"),
    path("tshirt/<shirt_id>/pay/", views.create_tshirt_checkout_session, name="shirt_pay"),
    path(
        "tshirt/<shirt_id>/pay/complete/",
        views.complete_tshirt_checkout_session,
        name="shirt_pay_complete",
    ),
    path("delete/", views.ProfileDeleteView.as_view(), name="profile_delete"),
]
