import unittest
from agentfit_ai.solar import AnalysisError, cited_to_profile
from agentfit_ai.profile import FIELDS

class CertaintyTests(unittest.TestCase):
    def candidate(self,field,value):
        fields=dict.fromkeys(FIELDS)
        fields[field]={"value":value,"evidenceLineIds":[1]}
        return fields

    def test_status_label_is_not_a_confirmed_technology(self):
        for field,value in (("database","미정"),("frontend",["React","미정"]),("ai",["검토 중"])):
            with self.subTest(field=field):
                with self.assertRaises(AnalysisError) as caught:
                    cited_to_profile("React 미정 검토 중","doc-1",self.candidate(field,value))
                self.assertEqual(caught.exception.code,"UNCONFIRMED_PROFILE_VALUE")
                self.assertEqual(caught.exception.field,field)

    def test_evaluation_before_operating_adoption_is_not_confirmed_ai(self):
        doc="문서 분석에는 Nova를 먼저 평가하며 운영 Provider 채택은 품질 검증 후 결정한다."
        with self.assertRaises(AnalysisError) as caught:
            cited_to_profile(doc,"doc-1",self.candidate("ai",["Nova"]))
        self.assertEqual(caught.exception.code,"UNCONFIRMED_PROFILE_VALUE")

    def test_confirmed_model_and_unrelated_candidate_are_separate(self):
        doc="Alpha를 운영 모델로 채택했다. Beta를 먼저 평가하며 운영 모델 채택은 검증 후 결정한다."
        result=cited_to_profile(doc,"doc-1",self.candidate("ai",["Alpha"]))
        self.assertEqual(result["data"]["ai"],["Alpha"])

    def test_completed_evaluation_and_selected_model_are_allowed(self):
        doc="Nova를 먼저 평가하고 운영 모델로 채택했다."
        result=cited_to_profile(doc,"doc-1",self.candidate("ai",["Nova"]))
        self.assertEqual(result["data"]["ai"],["Nova"])

    def test_status_word_in_project_name_is_preserved(self):
        result=cited_to_profile("프로젝트 이름은 미정으로 확정했다.","doc-1",self.candidate("project_name","미정"))
        self.assertEqual(result["data"]["project_name"],"미정")


    def test_another_models_pending_decision_does_not_reject_selected_model(self):
        doc="Alpha를 먼저 평가하고 운영에 채택했으며 Beta의 운영 모델 채택은 품질 검증 후 결정한다."
        result=cited_to_profile(doc,"doc-1",self.candidate("ai",["Alpha"]))
        self.assertEqual(result["data"]["ai"],["Alpha"])
