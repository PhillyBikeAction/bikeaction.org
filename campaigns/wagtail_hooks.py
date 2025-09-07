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
        """Custom index view with ordering by status then sort_order"""
        default_ordering = "status"  # Active campaigns first

    class CampaignPageListingViewSet(PageListingViewSet):
        """Custom page listing view for campaigns with status column"""

        menu_label = "Campaigns"
        menu_icon = "group"
        add_to_admin_menu = True
        model = CampaignPage
        index_view_class = CampaignPageIndexView

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
