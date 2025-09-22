from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db import models
from django.http import Http404
from modelcluster.contrib.taggit import ClusterTaggableManager
from modelcluster.fields import ParentalKey
from taggit.models import TaggedItemBase
from wagtail.admin.panels import FieldPanel
from wagtail.blocks import (
    BooleanBlock,
    CharBlock,
    ChoiceBlock,
    RawHTMLBlock,
    RichTextBlock,
    StructBlock,
)
from wagtail.contrib.routable_page.models import RoutablePageMixin, path
from wagtail.contrib.table_block.blocks import TableBlock
from wagtail.fields import RichTextField, StreamField
from wagtail.images.blocks import ImageBlock
from wagtail.images.models import Image
from wagtail.models import Page
from wagtail.models.media import Collection
from wagtail_link_block.blocks import LinkBlock

from pbaabp.forms import NewsletterSignupForm


class AlignedParagraphBlock(StructBlock):
    """
    RichTextBlock that can be aligned.
    """

    alignment = ChoiceBlock(
        choices=[("left", "Left"), ("center", "Center"), ("right", "Right")],
        default="left",
    )
    paragraph = RichTextBlock()

    class Meta:
        template = "blocks/aligned_paragraph.html"


class CardBlock(StructBlock):
    """
    A card with a header, text, and image
    """

    image = ImageBlock()
    image_side = ChoiceBlock(
        choices=[("left", "Left"), ("right", "Right")],
        default="left",
    )
    header = CharBlock(required=False)
    text = RichTextBlock()

    class Meta:
        template = "blocks/card.html"


class NewsletterSignupBlock(StructBlock):
    def get_context(self, value, parent_context=None):
        context = super().get_context(value, parent_context=parent_context)
        context["block_newsletter_form"] = NewsletterSignupForm(
            form_name="block", show_header=False
        )
        return context

    class Meta:
        template = "_block_newsletter_signup_partial.html"


class HomepageButtonBlock(StructBlock):
    """
    A button with text, a color, width, and optional icon
    """

    text = CharBlock()
    url = LinkBlock()
    color = ChoiceBlock(
        choices=[("pink", "Pink"), ("green", "Green")],
        default="pink",
    )
    width = ChoiceBlock(
        choices=[("full", "Full"), ("half", "Half")],
        default="full",
    )
    icon = CharBlock(
        required=False,
        help_text=(
            "A FontAwesome icon name, see "
            '<a href="https://fontawesome.com/search?ic=free">here</a> '
            "for list of options"
        ),
    )


class HomepageCardBlock(StructBlock):
    """
    A card with a title, subtitle, and text
    """

    text_side = ChoiceBlock(
        choices=[("left", "Left"), ("right", "Right")],
        default="right",
    )
    title = CharBlock()
    subtitle = CharBlock()
    text = RichTextBlock()

    class Meta:
        template = "blocks/homepage_card.html"


_features = [
    "anchor-identifier",
    "h2",
    "h3",
    "h4",
    "bold",
    "italic",
    "ol",
    "ul",
    "hr",
    "link",
    "document-link",
    "image",
    "embed",
    "code",
    "blockquote",
]

table_options = {
    "editor": "text",
    "renderer": "html",
    "contextMenu": [
        "row_above",
        "row_below",
        "---------",
        "col_left",
        "col_right",
        "---------",
        "remove_row",
        "remove_col",
        "---------",
        "undo",
        "redo",
        "---------",
        "copy",
        "cut",
        "---------",
        "alignment",
    ],
}


def get_collections():
    return [(collection.id, collection.name) for collection in Collection.objects.all()]


class DisplayCardsBlock(StructBlock):

    collection = ChoiceBlock(label="Collection to display", required=True, choices=get_collections)
    card_count_description = CharBlock(required=False)
    random_order = BooleanBlock(default=True, required=False)

    def get_context(self, value, parent_context=None):
        queryset = Image.objects.filter(collection=Collection.objects.get(id=value["collection"]))
        if value["random_order"]:
            queryset = queryset.order_by("?")
        context = super().get_context(value, parent_context=parent_context)
        context["images"] = queryset
        return context

    class Meta:
        template = "blocks/display_cards.html"


class FullSlugFieldPanel(FieldPanel):

    def __init__(self, field_name=None, heading=None, help_text=None, read_only=None, **kwargs):
        field_name = "get_url_parts" if not field_name else field_name
        heading = "Full URL" if not heading else heading
        help_text = "Takes into account parent slugs" if not help_text else help_text
        return super(FullSlugFieldPanel, self).__init__(
            field_name, heading=heading, help_text=help_text, read_only=True, **kwargs
        )

    def db_field(self):
        return None

    def format_value_for_display(self, value):
        value = value()
        if isinstance(value, list):
            return f"{value()[-1]}"
        elif isinstance(value, str):
            return value
        elif value is None:
            return "must set a slug and save first"


class CmsStreamPage(Page):

    show_title = models.BooleanField(default=True)

    body = StreamField(
        [
            ("card", CardBlock(features=_features)),
            ("paragraph", AlignedParagraphBlock(features=_features)),
            ("html", RawHTMLBlock()),
            ("table", TableBlock(table_options=table_options)),
            ("newsletter_signup", NewsletterSignupBlock()),
            ("display_card_block", DisplayCardsBlock()),
        ],
        use_json_field=True,
    )

    subpage_types = ["NavigationContainerPage", "CmsStreamPage"]

    content_panels = Page.content_panels + [
        FullSlugFieldPanel(),
        FieldPanel("show_title"),
        FieldPanel("body"),
    ]

    og_image = models.ForeignKey(
        "wagtailimages.Image", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    promote_panels = Page.promote_panels + [
        FieldPanel("og_image"),
    ]


class NavigationContainerPage(Page):
    """
    This page doesn't have HTML, and it works only to support hierarchical
    structure of the site.
    """

    class Meta:
        verbose_name = "Navigation Container Page"

    subpage_types = ["NavigationContainerPage", "CmsStreamPage"]


class PostPageTag(TaggedItemBase):
    content_object = ParentalKey("PostPage", related_name="tagged_items", on_delete=models.CASCADE)


class PostPage(Page):
    """
    A Post
    """

    author = models.CharField(max_length=128, default="Philly Bike Action")

    date = models.DateField()

    tags = ClusterTaggableManager(through=PostPageTag, blank=True)

    body = StreamField(
        [
            ("card", CardBlock(features=_features)),
            ("paragraph", AlignedParagraphBlock(features=_features)),
            ("html", RawHTMLBlock()),
            ("table", TableBlock(table_options=table_options)),
            ("newsletter_signup", NewsletterSignupBlock()),
        ],
        use_json_field=True,
    )

    content_panels = Page.content_panels + [
        FullSlugFieldPanel("canonical_url"),
        FieldPanel("author"),
        FieldPanel("date"),
        FieldPanel("tags"),
        FieldPanel("body"),
    ]

    def serve(self, request):
        if request.META["PATH_INFO"] != self.canonical_url():
            raise Http404
        return super().serve(request)

    def get_url_parts(self, request=None):
        parts = super().get_url_parts()
        return (parts[0], parts[1], self.canonical_url())

    def next_post(self):
        if self.pk is not None:
            return (
                PostPage.objects.live()
                .filter(date__gte=self.date)
                .exclude(slug=self.slug)
                .order_by("pk")
                .first()
            )
        return None

    def prev_post(self):
        if self.pk is not None:
            return (
                PostPage.objects.live()
                .filter(date__lte=self.date)
                .exclude(slug=self.slug)
                .order_by("-pk")
                .first()
            )
        return None

    def canonical_url(self):
        try:
            parent_part_url = self.get_parent().specific.get_url_parts()[-1]
            return (
                f"{parent_part_url}"
                f"{self.date.year:04}/{self.date.month:02}/{self.date.day:02}/"
                f"{self.slug}/"
            )
        except AttributeError:
            return None

    class Meta:
        verbose_name = "Post"


class PostsContainerPage(RoutablePageMixin, Page):
    """
    Displays recent posts, contains posts
    """

    posts_per_page = models.IntegerField(
        default=10, help_text="Number of posts to display per page"
    )

    content_panels = Page.content_panels + [
        FieldPanel("posts_per_page"),
    ]

    def get_posts(self, tag=None):
        posts = PostPage.objects.descendant_of(self).live().order_by("-date")
        if tag:
            posts = posts.filter(tags__name=tag)
        return posts

    def get_context(self, request):
        context = super().get_context(request)

        # Get tag from URL parameter
        tag = request.GET.get("tag")

        # Get all posts, ordered by date (newest first)
        posts = self.get_posts(tag=tag).order_by("-date")

        # Pagination
        page = request.GET.get("page", 1)
        paginator = Paginator(posts, self.posts_per_page)

        try:
            posts = paginator.page(page)
        except PageNotAnInteger:
            posts = paginator.page(1)
        except EmptyPage:
            posts = paginator.page(paginator.num_pages)

        context["posts"] = posts
        context["current_tag"] = tag

        # Get all tags used in posts with counts
        from django.db.models import Count
        from taggit.models import Tag

        context["all_tags"] = (
            Tag.objects.filter(cms_postpagetag_items__content_object__in=self.get_posts())
            .annotate(num_times=Count("cms_postpagetag_items"))
            .distinct()
            .order_by("name")
        )

        return context

    @path("<int:year>/")
    @path("<int:year>/<int:month>/")
    @path("<int:year>/<int:month>/<int:day>/")
    def post_by_date(self, request, year, month=None, day=None, *args, **kwargs):
        context = self.get_context(request)
        posts = self.get_posts().filter(date__year=year)
        if month:
            posts = posts.filter(date__month=month)
        if day:
            posts = posts.filter(date__day=day)

        # Apply pagination
        page = request.GET.get("page", 1)
        paginator = Paginator(posts, self.posts_per_page)

        try:
            posts = paginator.page(page)
        except PageNotAnInteger:
            posts = paginator.page(1)
        except EmptyPage:
            posts = paginator.page(paginator.num_pages)

        context["posts"] = posts
        return self.render(request, context_overrides=context)

    @path("tag/<slug:tag>/")
    def posts_by_tag(self, request, tag, *args, **kwargs):
        # Use regular get_context which handles tag via GET param
        request.GET = request.GET.copy()
        request.GET["tag"] = tag
        context = self.get_context(request)
        return self.render(request, context_overrides=context)

    @path("<int:year>/<int:month>/<int:day>/<slug:slug>/")
    def post_by_date_slug(self, request, year, month, day, slug, *args, **kwargs):
        post_page = self.get_posts().filter(slug=slug).first()
        if not post_page:
            raise Http404
        # here we render another page, so we call the serve method of the page instance
        return post_page.serve(request)

    class Meta:
        verbose_name = "Posts"

    subpage_types = ["PostPage"]


class HomePage(Page):

    def get_context(self, request):
        context = super().get_context(request)
        context["homepage_newsletter_form"] = NewsletterSignupForm(form_name="homepage")
        return context

    hero_background = models.ForeignKey(
        "wagtailimages.Image", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    hero_buttons_cta = models.CharField(max_length=128)
    hero_buttons = StreamField(
        [
            ("button", HomepageButtonBlock()),
        ]
    )

    hero_title = models.TextField()
    hero_text = RichTextField()

    body_background = models.ForeignKey(
        "wagtailimages.Image", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    body = StreamField(
        [
            ("homepagecard", HomepageCardBlock(features=_features)),
            ("paragraph", AlignedParagraphBlock(features=_features)),
            ("html", RawHTMLBlock()),
        ]
    )

    subpage_types = ["NavigationContainerPage", "CmsStreamPage", "PostsContainerPage"]
    # max_count_per_parent = 1
    content_panels = Page.content_panels + [
        FieldPanel("hero_background"),
        FieldPanel("hero_title"),
        FieldPanel("hero_text"),
        FieldPanel("hero_buttons_cta"),
        FieldPanel("hero_buttons"),
        FieldPanel("body_background"),
        FieldPanel("body"),
    ]
