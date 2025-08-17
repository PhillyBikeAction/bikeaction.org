{% load bleach_tags %}
# {{ application.data.shortname.value|bleach }}

**Quick Summary**:
```
{{ application.data.quick_summary.value|bleach }}
```

## Leader

**Name**:
```
{{ application.submitter.first_name }} {{ application.submitter.last_name }}
```

**Discord username**:
```
{{ application.submitter.profile.discord.extra_data.username }}
```

**{{ application.data.leader_preferred_contact_method.label }}**:
```
{{ application.data.leader_preferred_contact_method.value }}
```

**Past Experience**:
```
{{ application.data.leader_past_experience.value|bleach }}
```

## Overview

**{{ application.data.mission_relevance.label|bleach }}**:
```
{{ application.data.mission_relevance.value|bleach }}
```

**{{ application.data.success_criteria.label|bleach }}**:
```
{{ application.data.success_criteria.value|bleach }}
```

**{{ application.data.name_use.label|bleach }}**:
```
{{ application.data.name_use.value|bleach }}
```

**{{ application.data.recruitment.label|bleach }}**:
```
{{ application.data.recruitment.value|bleach }}
```

**{{ application.data.external_orgs.label|bleach }}**:
```
{{ application.data.external_orgs.value|bleach }}
```

## Logistics

**{{ application.data.location.label|bleach }}**:
```
{% if application.data.location.value %}{{ application.data.location.value|bleach }}{% else %}no response{% endif %}
```

**{{ application.data.time_and_date.label|bleach }}**:
```
{% if application.data.time_and_date.value %}{{ application.data.time_and_date.value|bleach }}{% else %}no response{% endif %}
```

**{{ application.data.recurring.label|bleach }}**:
```
{% if application.data.recurring.value %}Yes{% else %}No{% endif %}
```

## Resources

**{{ application.data.equipment_needed.label|bleach }}**:
```
{{ application.data.equipment_needed.value|bleach }}
```

**{{ application.data.volunteers_needed.label|bleach }}**:
```
{{ application.data.volunteers_needed.value|bleach }}
```

**{{ application.data.promotion_needed.label|bleach }}**:
```
{{ application.data.promotion_needed.value|bleach }}
```

**{{ application.data.finances_needed.label|bleach }}**:
```
{{ application.data.finances_needed.value|bleach }}
```

**{{ application.data.others_needed.label|bleach }}**:
```
{% if application.data.others_needed.value %}{{ application.data.others_needed.value|bleach }}{% else %}no response{% endif %}
```

## Anything Else

**{{ application.data.anything_else.label|bleach }}**:
```
{% if application.data.anything_else.value %}{{ application.data.anything_else.value|bleach }}{% else %}no response{% endif %}
```
