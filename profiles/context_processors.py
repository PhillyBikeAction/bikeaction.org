from profiles.forms import NewsletterSignupForm


def newsletter_form(request):
    return {"newsletter_form": NewsletterSignupForm()}
