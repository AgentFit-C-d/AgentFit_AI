import unittest
from agentfit_ai.field_role_schema import compatible, constrain_schema
from agentfit_ai.section_analysis import extraction_schema
from agentfit_ai.sections import split_sections

class FieldRoleTests(unittest.TestCase):
    def test_incompatible_pairs(self):
        self.assertFalse(compatible("features","product_fact","confirmed"))
        self.assertFalse(compatible("frontend","user_action","confirmed"))
        self.assertFalse(compatible("database","product_fact","absent"))
        self.assertFalse(compatible("ai","client","absent"))
    def test_valid_and_exclusion_pairs(self):
        self.assertTrue(compatible("features","user_action","confirmed"))
        self.assertTrue(compatible("external_integrations","named_service","absent"))
        self.assertTrue(compatible("ai","client","confirmed"))
    def test_schema_matches_rule_and_does_not_mutate(self):
        import copy
        base=extraction_schema(split_sections("x"),quote_only=True)
        before=copy.deepcopy(base)
        schema=constrain_schema(base)
        self.assertEqual(base,before)
        branches=schema["properties"]["sections"]["items"]["properties"]["facts"]["items"]["anyOf"]
        from agentfit_ai.section_analysis import ALL_ROLES,STATUSES
        from agentfit_ai.profile import FIELDS
        for f in FIELDS:
            for r in ALL_ROLES:
                for s in STATUSES:
                    allowed=any(f in b["properties"]["field"]["enum"] and r in b["properties"]["role"]["enum"] and s in b["properties"]["status"]["enum"] for b in branches)
                    self.assertEqual(allowed,compatible(f,r,s))
