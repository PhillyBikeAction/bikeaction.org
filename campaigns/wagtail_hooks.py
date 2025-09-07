"""
Wagtail hooks for campaigns app.
"""

from django.utils.html import format_html
from wagtail import hooks
from wagtail.admin.ui.tables import Column
from wagtail.admin.views.pages.listing import IndexView
from wagtail.admin.viewsets.pages import PageListingViewSet


@hooks.register("register_admin_viewset")
def register_campaign_page_listing_viewset():
    """Register custom viewset for CampaignPage listings"""
    from campaigns.wagtail_models import CampaignPage

    class CampaignPageIndexView(IndexView):
        """Custom index view with ordering by status and sort button"""

        default_ordering = "status"  # Active campaigns first, then by page tree order

        def get_header_buttons(self):
            """Add reorder button to the listing header"""
            buttons = super().get_header_buttons()
            from django.urls import reverse
            from wagtail.admin.widgets.button import Button

            from campaigns.wagtail_models import CampaignsIndexPage

            # Get the campaigns index page
            index_page = CampaignsIndexPage.objects.first()
            if index_page:
                # Link to the page explorer for the index page with sort menu
                explorer_url = reverse("wagtailadmin_explore", args=[index_page.id])
                # Create button widget
                sort_button = Button(
                    "Sort menu order",
                    url=explorer_url + "?ordering=ord",
                    icon_name="order",
                    classname="w-header-button button",
                    attrs={"title": "Reorder campaigns within their status groups"},
                )
                buttons.append(sort_button)
            return buttons

    class CampaignPageListingViewSet(PageListingViewSet):
        """Custom page listing view for campaigns with status column"""

        menu_label = "Campaigns"
        menu_icon = "group"
        add_to_admin_menu = True
        model = CampaignPage
        index_view_class = CampaignPageIndexView
        ordering = ["status", "sort_order"]  # Enable sort menu order within status groups

        columns = PageListingViewSet.columns + [
            Column(
                "status_display",
                label="Status",
                accessor="specific.get_status_display_formatted",
                classname="campaign-status",
            ),
        ]

        def get_queryset(self):
            """Filter to only CampaignPage instances"""
            queryset = super().get_queryset()
            return queryset.type(CampaignPage).specific()

    return CampaignPageListingViewSet("campaign_pages")


@hooks.register("insert_global_admin_css")
def global_admin_css():
    """Add custom CSS for campaign status display"""
    return format_html(
        "<style>"
        ".campaign-status-draft {{ color: #999; }}"
        ".campaign-status-active {{ color: #28a745; font-weight: bold; }}"
        ".campaign-status-completed {{ color: #007bff; }}"
        ".campaign-status-canceled {{ color: #dc3545; }}"
        ".campaign-status-suspended {{ color: #ffc107; }}"
        "</style>"
    )
