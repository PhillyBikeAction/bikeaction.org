from django.urls import path

from facets import views

urlpatterns = [
    path("find/", views.index),
    path("search/", views.query_address, name="rco_search"),
    path("report/", views.report),
    path("list/", views.rco_list, name="rco_list"),
    path("rco/<str:rco_id>/", views.rco, name="rco_detail"),
    path("rco_detail/<str:rco_id>/", views.rco_detail, name="rco_staff_detail"),
    path("custom/list/", views.custom_list, name="custom_list"),
    path("custom_detail/<str:custom_id>/", views.custom_detail, name="custom_staff_detail"),
    path("all/", views.all_profiles, name="all_profiles"),
]
