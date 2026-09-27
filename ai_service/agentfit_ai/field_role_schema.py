"""Opt-in structural constraints; these do not infer semantic correctness."""
from copy import deepcopy
from .evidence import ROLES
from .profile import ARRAY_FIELDS
EXCLUDED_ROLES = ("development_task", "technical_description", "client", "generic_source")
NORMAL_STATUSES = ("confirmed", "tentative", "negated", "historical")

def compatible(field, role, status):
    if field not in ROLES:
        return False
    if status == "absent":
        return field in ARRAY_FIELDS and role in ROLES[field]
    return status in NORMAL_STATUSES and role in (*ROLES[field], *EXCLUDED_ROLES)

def constrain_schema(schema):
    result = deepcopy(schema)
    facts = result["properties"]["sections"]["items"]["properties"]["facts"]
    original = facts["items"]
    branches = []
    for field, roles in ROLES.items():
        item = deepcopy(original)
        item["properties"]["field"]["enum"] = [field]
        item["properties"]["role"]["enum"] = [*roles, *EXCLUDED_ROLES]
        item["properties"]["status"]["enum"] = list(NORMAL_STATUSES)
        branches.append(item)
        if field in ARRAY_FIELDS:
            absent = deepcopy(item)
            absent["properties"]["role"]["enum"] = list(roles)
            absent["properties"]["status"]["enum"] = ["absent"]
            branches.append(absent)
    facts["items"] = {"anyOf": branches}
    return result
