import os

import markdown
import pynliner
from anymail.message import attach_inline_image_file
from bs4 import BeautifulSoup
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template import TemplateDoesNotExist, TemplateSyntaxError, engines
from django.template.loader import get_template

from profiles.models import DoNotEmail

HEADER = """
    <div class="email-header">
      <a href="https://bikeaction.org/"
         aria-label="Philly Bike Action! Home">
        <img class="email-header-img"
             alt="Philly Bike Action!"
             src="templates/email/header-img.png">
      </a>
    </div>
"""

FOOTER = """
    <div class="footer">
      <table style="text-align: center; color: white; font-family: sans-serif;">
        <tr>
          <td style="width: 50%; padding: .5em;">
            <img style="padding: 1em;"
                 class="email-header-img"
                 alt="Philly Bike Action!"
                 src="templates/email/footer-img.png">
            <p>Safe, usable, protected, interconnected bike infrastructure for Philadelphia.</p>
            <span>
              <a style="text-decoration: none; color: white;"
                 href="mailto:info@bikeaction.org">
                📧 info@bikeaction.org
              </a>
            </span>
          </td>
          <td style="width: 50%; padding: .5em;">
            <b>Find us on Social Media</b><br>
              <a class="social-icon"
                 aria-label="@phlbikeaction on twitter"
                 href="https://twitter.com/phlbikeaction">
                <img class="footer-icon" src="templates/email/twitter-logo-24.png">
              </a>
              <a class="social-icon"
                 aria-label="@phlbikeaction on instagram"
                 href="https://www.instagram.com/phlbikeaction/">
                <img class="footer-icon" src="templates/email/instagram-logo-24.png">
              </a><br>
            <b>Join our Discord</b><br>
              <a class="social-icon"
                 aria-label="Philly Bike Action Discord"
                 href="https://discord.gg/FNYfjzjWnB">
                <img class="footer-icon" src="templates/email/discord-logo-24.png">
              </a>
           </td>
        </tr>
        <tr>
          <td colspan=2>
            <p>
                Want to stop receiving these emails?
                Delete your profile
                <a href="https://bikeaction.org/accounts/profile/">here</a>.
            </p>
          </td>
        </tr>
      </table>
    </div>
"""


def template_from_string(template_string, using=None):
    """
    Convert a string into a template object,
    using a given template engine or using the default backends
    from settings.TEMPLATES if no engine was specified.
    """
    # This function is based on django.template.loader.get_template,
    # but uses Engine.from_string instead of Engine.get_template.
    chain = []
    engine_list = engines.all() if using is None else [engines[using]]
    for engine in engine_list:
        try:
            return engine.from_string(template_string)
        except TemplateSyntaxError as e:
            chain.append(e)
    raise TemplateSyntaxError(chain)


def send_email_message(
    template_name,
    from_,
    to,
    context,
    subject_template=None,
    message=None,
    subject=None,
    attachments=None,
    reply_to=None,
):
    """
    Send an email message.

    :param template_name: Use to construct the real template names for the
    subject and body like this: "email/%(template_name)s/subject.txt"
    and "email/%(template_name)s/body.txt"
    :param from_: From address to use
    :param to: List of addresses to send to
    :param context: Dictionary with context to use when rendering the
    templates.
    :param subject_template: optional string to use as the subject template, in place of
       email/{{ template_name }}/subject.txt
    """
    # Filter out emails in DoNotEmail list
    filtered_to = []
    for email in to:
        try:
            DoNotEmail.objects.get(email=email)
            # Email is in DoNotEmail list, skip it
            continue
        except DoNotEmail.DoesNotExist:
            # Email not in do-not-email list, include it
            filtered_to.append(email)

    # If all emails were filtered out, don't send anything
    if not filtered_to:
        return

    # Update the to list to only include allowed emails
    to = filtered_to

    if from_ is None:
        from_ = settings.DEFAULT_FROM_EMAIL

    if subject is None:
        if subject_template is not None:
            subject_template = get_template(subject_template)
        else:
            name = f"email/{template_name}/subject.txt"
            subject_template = get_template(name)

        subject = subject_template.render(context)
    else:
        subject = subject

    subject = " ".join(subject.splitlines()).strip()

    if hasattr(settings, "EMAIL_SUBJECT_PREFIX"):
        subject = f"{settings.EMAIL_SUBJECT_PREFIX} {subject}"

    if message is None:
        try:
            _ = get_template(template_name)
        except TemplateDoesNotExist:
            _ = get_template(f"email/{template_name}/body.txt")
            template_name = f"email/{template_name}/body.txt"

        message = get_template(template_name).render(context)
    else:
        message = template_from_string(message).render(context)

    html = markdown.markdown(message)
    html = HEADER + '<div class="content">' + html + "</div>" + FOOTER

    soup = BeautifulSoup(html, "html")

    mail = EmailMultiAlternatives(
        subject,
        message,
        from_,
        to,
        reply_to=reply_to,
    )
    mail.mixed_subtype = "related"

    for img in soup.findAll("img"):
        cid = attach_inline_image_file(mail, img["src"])
        img["src"] = "cid:" + cid

    inliner = pynliner.Pynliner().from_string(str(soup))
    with open(os.path.join(os.path.dirname(__file__), "email.css")) as css:
        inliner = inliner.with_cssString(css.read())
    html = inliner.run()

    mail.attach_alternative(
        '<table border="0" cellspacing="0" width="100%"><tr><td></td><td width="600">'
        + html
        + "</td><td></td></tr></table>",
        "text/html",
    )

    if attachments is not None:
        for attachment in attachments:
            mail.attach(*attachment)

    mail.send()
