from django.urls import path

from release import views

urlpatterns = [
    path("<slug:release_slug_or_id>/", views.release_view),
    path("<slug:release_slug_or_id>/signature/", views.release_signature, name="release_signature"),
    path(
        "<slug:release_slug_or_id>/kiosk-postroll/",
        views.release_signature_kiosk_postroll,
        name="release_signature_kiosk_postroll",
    ),
]
