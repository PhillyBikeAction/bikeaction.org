{% load bleach_tags %}
# Community Action Fund Application

# {{ application.data.project_title.value|bleach }}

## Contact Information
**{{ application.data.primary_contact_name.label|bleach }}**: {{ application.data.primary_contact_name.value|bleach }}

**{{ application.data.organization.label|bleach }}**: {{ application.data.organization.value|default:"Not provided"|bleach }}

**{{ application.data.email.label|bleach }}**: {{ application.data.email.value|bleach }}

**{{ application.data.phone.label|bleach }}**: {{ application.data.phone.value|bleach }}

## Project
**{{ application.data.project_description.label|bleach }}**
```
{{ application.data.project_description.value|bleach }}
```

## Community Impact
```
{{ application.data.community_impact.value|bleach }}
```

## Project Readiness
```
{{ application.data.project_readiness.value|bleach }}
```

## Budget
**{{ application.data.amount_requested.label|bleach }}**: ${{ application.data.amount_requested.value|bleach }}

**{{ application.data.estimated_total_project_cost.label|bleach }}**: ${{ application.data.estimated_total_project_cost.value|bleach }}

## Funding Needs
**{{ application.data.funding_preference.label|bleach }}**: {{ application.data.funding_preference.value|bleach }}

{% if application.data.funding_preference_explanation.value %}
```
{{ application.data.funding_preference_explanation.value|bleach }}
```
{% endif %}

{% if application.supporting_materials.exists %}
## Supporting Materials
{% for material in application.supporting_materials.all %}
- [{{ material.filename }}](<{{ material.file.url }}>)
{% endfor %}
{% endif %}
