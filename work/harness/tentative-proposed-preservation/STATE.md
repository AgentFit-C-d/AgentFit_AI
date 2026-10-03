# tentative/proposed preservation

- 사용자 승인: 미정 후보 서버제외만 수정, raw·지침·계약·검토·골드 그대로, 모델·외부네트워크0, 큰Goalpaused.
- 기준 branch feature/role-context-ab 3d0bbee에서 feature/tentative-proposed-preservation 생성. 기존 semantic-confirmation-guard STATE와 untracked 자료 보존.
- 원인조사: _decision의 마지막 제외 조건에 commitment != adopted가 포함돼 tentative/proposed가 마지막 status 분기에 도달하지 못함. 원문/역할/축은 저장응답으로 재현 예정.
- 최종 경계: project_candidate_profile → 기존 metadata(sourceValue/documentId) → project_candidate_confirmation. 실제 pipeline은 이 앞에서 GLM검토를 실행하므로 해당 응답이 없는 이번자료로 전체 성공을 꾸미지 않음. 미검토 합성 envelope를 사용하는 경계 단독시험으로 표시.
- SDD: specs/ai-developer/tentative-proposed-preservation/{spec,plan,tasks}. 이미 승인된 범위로 구현/검증 계속, 재승인없음.
- 기본 exec setup refresh 오류는 승인된 escalated rtk로 읽기/로컬 실행. .env열람0, 새로운 모델호출0.
- T1 완료: 원래32행서버결과 일치. D2C006 A/B 지원347:401/값356:365, target/current/positive/product_fact/외부연동/external_service/tentative/proposed. 마지막 제외분기의 commitment!=adopted만 true. before.json 및 원본24파일 별도해시fixture 보존.
- T2 RED: 신규12테스트 중5실패로 미정보존/최종경계 문제확인. 로그 output/tentative-proposed-preservation-20261003-v1/tests-102406479221.txt.
- T2 최소수정: 부정/범위/시점/field/status제외 뒤 commitment검사를 분리. 알려진일치역할+tentative/proposed만 needs_confirmation. supported승격0, 원시판단변경0. 기존 guard순서 유지. 신규12개 GREEN,99792enum조합 중 의도10조합만변경.
- 최종확인 경계는 실제검토결과없는 단일후보를 coverage_verified=False,전필드unresolved인 합성envelope로만검사. 성공review/GLM응답을주입하지않음. 원문값/위치/documentId/질문과 보류 보존, 긍정값채택거부검증. 기존질문10개는미검토조건에서유지되고 실사용확인부담지표로사용하지않음.
- 전체테스트진행중. 외부DNS/소켓차단 guard를 부모·Python자식에전달하고 키환경변수제거. loopback테스트만허용. 모델·외부통신0.
- 전체첫실행1500개: failures2/errors9는 모두 기존복구검사 CODE_MISMATCH. 현재분류서버코드가동결된과거재개실행과달라 정상적으로재개거부됨. 별도 예상실패였던 proposed보류 테스트1개가 unexpected success로 바뀌어 해당 expectedFailure만제거해정상필수회귀로승격한다. 기존 모델오류expectedFailure4개와 플랫폼skip7개는변경하지않음.
- 복구 hash검증/원본seal/worker는수정하지않는다. 이 실패를덮기위해코드해시를업데이트하거나재개를허용하지않음. 관련 v3/위치테스트는전체로그에서통과했고 별도최종검증예정.
- 최종 선택 회귀: 60개 실행, 56개 통과·기존 모델 오류 예상 실패 4개. 신규12/12, 역할18(14pass+4xfail), anchor12/12, v3보존12/12, worker/HTTP/mock6/6. 새로운 skip/기준완화 없음.
- verify_final.py: fixture24개·보호파일208개 불변, 현재 제품 파일은 after.json hash와 동일. 구 D2 파생 records는 현재판정과 달라 거부되며 원시응답 재검증은 성공. 원본수정/버전혼용 금지로 보고.
- 실제 저장32행: supported13유지, needs_confirmation10→12, excluded9→7. 변화는 D2C006 A/B뿐. 최종경계는 sourceValue/위치/documentId/질문 유지·긍정승격거부. 후속 실제검토/전체결과 미측정.
- 결과 문서: specs/ai-developer/tentative-proposed-preservation/results.md. 전체검증실패11건을 숨기지 않으며 안전검사유지. 큰Goal get_goal 결과 paused 확인. 새호출/외부전송/서비스적용0.
- 독립 읽기 전용 리뷰 완료: 코드 결함 없음. 구 파생 판정의 거부 및 경계 검사가 실제 unresolved 전파를 입증하지 않는 한계 반영. 로컬 커밋만 준비, 사용자 외부전송금지로 push하지 않음.
