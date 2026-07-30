from django.urls import path

from community_fund import views


urlpatterns = [
    path("application/", views.application, name="community_action_fund_application"),
    path(
        "application/<pk>/edit/", views.application, name="community_action_fund_application_edit"
    ),
    path(
        "application/<pk>/delete/",
        views.application_delete,
        name="community_action_fund_application_delete",
    ),
    path(
        "application/<pk>/view/",
        views.application_view,
        name="community_action_fund_application_view",
    ),
]
