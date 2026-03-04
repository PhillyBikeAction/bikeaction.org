import json
import re

import httpx


def parse_html_form(html_content):
    """Parse HTML form to extract select fields and their options."""
    mapping = {}

    # Find all select elements
    select_pattern = r'<select[^>]*name="([^"]*)"[^>]*>(.*?)</select>'

    for select_match in re.finditer(select_pattern, html_content, re.DOTALL):
        name = select_match.group(1)
        select_content = select_match.group(2)
        select_start = select_match.start()

        # Look backwards for the nearest label (within 500 chars before select)
        context_start = max(0, select_start - 500)
        context = html_content[context_start:select_start]

        # Find the last label in this context
        label_matches = list(re.finditer(r"<label[^>]*>(.*?)</label>", context, re.DOTALL))
        if label_matches:
            label_text = label_matches[-1].group(1)
            # Clean up label text (remove HTML tags, extra whitespace, asterisks)
            label = re.sub(r"<[^>]+>", "", label_text)
            label = re.sub(r"\s+", " ", label).strip("*").strip()
        else:
            label = name

        # Extract all option text (skip empty ones)
        option_pattern = r"<option[^>]*>([^<]+)</option>"
        options = []
        for opt_match in re.finditer(option_pattern, select_content):
            text = opt_match.group(1).strip()
            # Skip placeholder/empty options
            if text and text.lower() not in ["select", "please select", "---", ""]:
                options.append(text)

        if options and label:
            mapping[label] = options

    return mapping


r = httpx.get("https://ppa-forms-neu.powerappsportals.com/Mobility-Access-Request/")
form_mapping_json = parse_html_form(r.text)

print(json.dumps(form_mapping_json, indent=2))
