import unittest
from agentfit_ai.profile import FIELDS
from agentfit_ai.evidence import EvidenceError, resolve_quote, evidence_to_profile

def fact(value, quote=None, context=None, role="product_fact"):
    return {"value":value,"quote":quote or value,"context":context,"role":role}
def confirmed(*items):
    return {"state":"confirmed","items":list(items)}
def candidate(field, value):
    return dict(dict.fromkeys(FIELDS),**{field:value})

class EvidenceContractTests(unittest.TestCase):
    def test_unique_exact_quote_uses_codepoint_offsets(self):
        doc=chr(0x1f600)+"\r\nPython"
        self.assertEqual(resolve_quote(doc,"Python",None),{"start":3,"end":9})
    def test_ambiguous_quote_never_picks_first(self):
        with self.assertRaises(EvidenceError) as caught:resolve_quote("Go then Go","Go",None)
        self.assertEqual(caught.exception.reason,"AMBIGUOUS_QUOTE")
        self.assertEqual(caught.exception.match_count,2)
    def test_context_disambiguates(self):
        self.assertEqual(resolve_quote("demo Go; server Go","Go","server Go"),{"start":16,"end":18})
    def test_context_must_be_unique_and_contain_unique_quote(self):
        for doc,quote,context in [("Go Go","Go","Go Go"),("x Go x Go","Go","x Go"),("Go","Go","missing"),("Go","Go","G")]:
            with self.subTest(doc=doc,context=context),self.assertRaises(EvidenceError):
                resolve_quote(doc,quote,context)
    def test_no_fuzzy_or_normalized_matching(self):
        for quote in ["book  search","search book","Book search"]:
            with self.subTest(quote=quote),self.assertRaises(EvidenceError):
                resolve_quote("book search",quote,None)
    def test_overlap_is_ambiguous(self):
        with self.assertRaises(EvidenceError) as caught:resolve_quote("aaa","aa",None)
        self.assertEqual(caught.exception.match_count,2)
    def test_each_field_has_identical_exact_evidence(self):
        arrays={"frontend","backend","ai","features","external_integrations"}
        for field in FIELDS:
            role="user_action" if field=="features" else "named_service" if field=="external_integrations" else "operating_model" if field=="ai" else "product_fact"
            p=evidence_to_profile("Alpha","doc",candidate(field,confirmed(fact("Alpha",role=role))))
            self.assertEqual(p["data"][field],["Alpha"] if field in arrays else "Alpha")
            self.assertEqual(p["evidence"][field],[{"documentId":"doc","start":0,"end":5}])
    def test_value_must_be_supported_by_its_own_quote(self):
        with self.assertRaises(EvidenceError):
            evidence_to_profile("Python and Go","doc",candidate("backend",confirmed(fact("Go","Python"))))
    def test_duplicate_values_are_rejected(self):
        with self.assertRaises(EvidenceError) as caught:
            evidence_to_profile("Go","doc",candidate("backend",confirmed(fact("Go"),fact("Go"))))
        self.assertEqual(caught.exception.reason,"DUPLICATE_VALUE")
        self.assertEqual(caught.exception.index,1)
    def test_absence_and_unknown_remain_distinct(self):
        p=evidence_to_profile("no integrations","doc",candidate("external_integrations",{"state":"absent","quote":"no integrations","context":None}))
        self.assertEqual(p["data"]["external_integrations"],[])
        self.assertIsNone(p["data"]["backend"])
        self.assertIn("backend",p["unknownFields"])
    def test_scalar_absence_and_wrong_role_rejected(self):
        for field,item in [("database",{"state":"absent","quote":"none","context":None}),("features",confirmed(fact("none",role="product_fact")))]:
            with self.subTest(field=field),self.assertRaises(EvidenceError):
                evidence_to_profile("none","doc",candidate(field,item))
    def test_bad_shapes_and_empty_confirmed_fail_closed(self):
        for item in [{"state":"confirmed","items":[]},{"state":"unknown","items":[]},confirmed(dict(fact("Go"),extra="ignore"))]:
            with self.subTest(item=item),self.assertRaises(EvidenceError):
                evidence_to_profile("Go","doc",candidate("backend",item))

    def test_generated_prefixes_preserve_offsets_and_ambiguity(self):
        for prefix in ["", "x", " ", "\r\n", chr(0x1f600), "e"+chr(0x301)]:
            for word in ["Go", "aa", "book search", chr(0xD55C)]:
                with self.subTest(prefix=prefix,word=word):
                    doc=prefix+"["+word+"]"
                    span=resolve_quote(doc,word,None)
                    self.assertEqual(doc[span["start"]:span["end"]],word)
                    self.assertEqual(span["start"],len(prefix)+1)
                    repeated=doc+"; selected:"+word
                    with self.assertRaises(EvidenceError):resolve_quote(repeated,word,None)
                    span=resolve_quote(repeated,word,"selected:"+word)
                    self.assertEqual(span["start"],len(doc)+len("; selected:"))
