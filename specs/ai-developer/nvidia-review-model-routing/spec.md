# NVIDIA 검토 모델 선택 비교

## 근거와 목적

진단 평가 PUBLIC-01/run0에서 DeepSeek4.1Flash 추출·분류11회는 전송 완료됐지만 첫 GLM5.3 커버리지 검토가302.213초 뒤 HTTP5xx로 실패했다. 최종 Profile은 없었다. 모델의 일반적인 의미 성능을 단정하지 않고, **검토 모델 선택만 바꾼 별도 평가**로 이 실행 경로를 비교한다.

후보 추출·분류·기능 단계는 기존 DeepSeek, 기본 서비스 검토는 기존 GLM을 유지한다. `--call-diagnostics --review-model deepseek-ai/deepseek-v4.1-flash`를 명시한 평가만 DeepSeek 검토를 사용한다. 기존 함수의 review_model 옵션을 내부 프로세스 경계까지 전달하는 한정된 변경이다. 사용자의 목표 내 자율 설계·직접 구현 승인을 적용하고, SDD/feature별 push를 유지한다.

## 계약

- 명시적 선택은 진단을 켠 NVIDIA 평가에서만 허용한다. 허용 모델은 현재 무료 확인 범위인 DeepSeek4.1Flash와 GLM5.3 두 개이며, 임의 문자열/타입/다른 서비스 모드/진단 없는 선택은 키 로딩·자식 시작·모델 호출 전에 거절한다.
- 기본 인자가 없으면 기존 요청 packet·모델·응답·동작을 유지한다. 공개 HTTP API/Profile/서비스 환경 변수는 추가하지 않는다.
- 평가의 review_model → 부모 nvidia_review_model → 내부 `reviewModel` 문자열 → execute_nvidia_analysis(review_model) → 기존 analyze_nvidia_candidates(review_model)로 전달한다. 자식도 같은 모드·진단·모델 제한을 검사한다.
- DeepSeek 선택 실험의 식별자는 `nvidia-deepseek-review-v1`, freeze/run/summary도 같은 접두사를 사용한다. 명시 GLM은 기존 진단 모드와 동일한 설정이므로 기존 진단 식별자를 유지한다. 선택 없음은 기본 NVIDIA/진단 모드의 기존 메타데이터를 유지한다.
- 새 freeze에 선택 모델·기존 진단 태그·전체 코드 해시·원문/gold/scorer를 고정한다. CLI·준비 결과·재개 시 식별자를 다시 검증하고 다른 모델/freeze/결과 폴더 혼합은 거절한다.
- 진단의 검토 단계 요청 모델은 선택과 같아야 하고 나머지 모델 호출은 기존 DeepSeek이어야 한다. 부모의 명시적 선택 응답과 evaluator의 결과 행에서 검증하며 모순된 메타데이터를 결과로 채택하지 않는다.
- 추출/검토 프롬프트·필드 계약·근거·채점·최대64호출·1800초·재시도0·제공자 오류 중단·무료 확인은 그대로다. 기존 모델별 payload 변환은 선택 모델에 적용하되 새 튜닝을 섞지 않는다.
- 이전 실제 세 결과 폴더와 gold/freeze/기준 커밋은 보존한다. 이전 종료 실험을 재시작하거나 성공 결과로 덮어쓰지 않는다.

## 검증 기준

1. 허용/거절 입력과 기본 요청 불변을 실제 자식 프로토콜로 확인한다. 모드나 진단 없는 선택은 시작0회다.
2. 실제 SDK·자식·loopback에서 같은 합성 문서의 기본5호출(DeepSeek3→GLM1→DeepSeek1)과 선택5호출(DeepSeek5)이 점수·계약·호출 수를 유지한다. 검토 모델만 바뀌어야 한다.
3. 선택 검토의503/429에서1회 실패 후 멈추고 진단을 보존한다. 잘못된 응답 모델/진단·손상된 행·다른 manifest는 거절한다.
4. 오프라인 preflight는 키·API 없이 새freeze10문서/207임시gold를 검증한다. strict checkpoint·실패 후 재시작 금지와 기존 회귀 검사를 유지한다.
5. 단위/runtime/계약/core suite와 단일 독립 최종 리뷰를 거쳐 feature push·정확한 코드SHA CI를 확인한다. 실제 품질 향상은 별도 실제 결과로만 판단한다.

## 예산

구현·로컬 검증: 외부0/유료0/재시도0/배포0. 합성 요청30초·대상120초·suite180초·CI10분·구현60분마다 점검. 이후 실제 비교는 별도 예산·새 결과 폴더로 등록하며 현재 무료 확인의 원래 만료를 연장하거나 새로운 확인으로 꾸미지 않는다. 사람 gold/실제Spring/운영 검증은 계속 미완료다.
