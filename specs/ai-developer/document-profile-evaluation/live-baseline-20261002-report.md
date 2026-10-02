# AgentFit 기획서 단일 기준 평가 결과

## 실행 결과

- 평가 코드: `274ec06`. 현재 `integrated-nvidia` 경로, 원문 1개, 실행 1회. U/US 미삽입, 저장 후보 주입 없음.
- 실제 요청 **25회**, 총 **1,762.135초(29분 22초)**, 재시도 **0회**, 호출 실패 **0회**. DeepSeek 22회·GLM 3회.
- 상한 50회·전체 1,800초·요청당 600초를 준수했다. 마지막 요청은 남은 시간 451.520초에서 제한을 449.520초로 낮췄고 413.439초에 반환했다.
- 최종 결과는 `needs_confirmation / REVIEW_CONFIRMATION_REQUIRED`. 정상적인 확인 요청 결과이며 전송 실패가 아니다. 자동 사용자 확정·저장·서비스 적용은 실행하지 않았다.
- 사용자에게 무료로 확인된 NVIDIA `https://integrate.api.nvidia.com/v1/chat/completions`의 DeepSeek 4.1 Flash와 GLM 5.3만 사용했다. 유료 전환·충전·대체 호출 없음.
- 분석 코드·지침·스키마·원문·골드의 동결 해시가 실행 후에도 일치했다. 시간·요청 제한은 실행 도우미에서만 적용했다. HTTP 전송은 기존 SSE 해석을 그대로 쓰는 요청별 자식 프로세스로 제한했다.
- 시간은 분석 프로세스의 실제 실행 시간이다. 사전 파일 준비와 이후 오프라인 수동 채점 시간은 포함하지 않는다. 관측 기록 작업은 약 0.099초였다.

## 정상 의미 40개 결과

| 범위 | 보존 | 보류 | 누락 | 사람 검토 필요 | 합계 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 기능 외 정상 사실 | 2 | 2 | 0 | 0 | 4 |
| 세부 기능 의미 | 24 | 7 | 3 | 2 | 36 |
| 전체 | **26 (65%)** | **9 (22.5%)** | **3 (7.5%)** | **2 (5%)** | **40** |

- 보존: 최종 Profile 값으로 세부 의미가 남아 있음. 사용자 확정이나 설치·저장 성공을 뜻하지 않는다.
- 보류: Profile 값만으로는 충분하지 않지만, 해당 의미의 원문 값·위치와 `needs_confirmation` 후보가 최종 응답에 남아 있음.
- 누락: Profile 값과 명시적인 확인 필요 후보에 해당 세부 의미가 없음. 단순 감사 메타데이터에 원래 후보가 남은 것은 별도로 표시했다.
- 사람 검토 필요: 원문 정답을 바꾼 것이 아니라 출력이 세부 의미를 충분히 담는지 애매한 경우다. F06.01(역할·업무 수집)과 F08.01(Catalog 검토)을 통과·실패 어느 쪽으로도 강제하지 않았다.
- 기능 반환값은 23개 문자열이다. 목록 수를 36개 의미의 성능 점수로 사용하지 않았다. 동일 문자열이 여러 의미를 담으면 각각 근거를 대조했다.

## 10개 필드: 기대값과 실제 값

모든 `fieldStates`가 `unresolved`다. 값이 보존된 필드도 초안이다. 위치 연결에서 탈락한 후보가 있으면 기존 확인 투영 규칙이 10필드 전체를 재확인 대상으로 올린다.

| 필드 | 동결 기대값 | 실제 Profile 값 | 판단 |
| --- | --- | --- | --- |
| project_name | AgentFit | null | 보류 후보에 AgentFit이 남았지만 값은 빠짐 |
| project_type | 웹 서비스 | 웹 서비스 | 값 보존 |
| domain | AI 개발 도구와 설정 | null | 도메인을 other로 분류. AI 개발 도구가 미할당 확인 후보에 남음 |
| frontend | 미정(null) | null | 미정 유지 |
| backend | 미정(null) | null | 미정 유지; Modular Monolith는 확인 후보에만 있음 |
| ai | 미정(null) | null | 미정 유지; Solar Pro 4는 평가 후보로 보류 |
| database | 미정(null) | null | 미정 유지 |
| deployment | 미정(null) | null | 미정 유지 |
| features | 36개 세부 의미 / 16개 대표 묶음 | 23개 기능 표현 — 아래 실제 값 목록 | 23개 실제 값은 아래에 원문 그대로 제시. 36개 의미 중 24 보존·7 보류·3 누락·2 검토 필요 |
| external_integrations | ["GitHub"] | ["GitHub", "Codex"] | GitHub 보존, Codex 오분류 1건 |

### 실제 features 값 23개

1. 현재 조건에 맞는 최소 구성을 제안한다
2. 추천 이유·권한·바뀔 내용을 확인하고 승인한 설정과 적용 안내를 받는다
3. 결과에 필요한 정보는 단계별로 확인하며
4. 확인하지 못한 부분은 결과에도 표시한다
5. 문서를 구조화하고 역할에 필요한 작업 능력을 정리
6. 호환 조건·중복·충돌·추가 준비를 확인
7. 변경 내용, 인증과 적용 방법, 실패 시 다음 행동 안내
8. 수정 가능한 Project Profile, 미정 항목, 출처·근거 위치
9. 필요한 작업과 현재 조건에 대한 정리
10. 필요한 최소 구성, 이유·조건·권한 또는 추가 도구 불필요 판단
11. 대상 경로·설정 내용·확인 범위에 맞는 변경안과 충돌 정보
12. 승인 내용과 일치하는 설정 파일, 적용·인증·무해한 사용 확인 안내
13. 누가 어떤 범위와 버전을 확인했는지에 따른 상태
14. 실제 환경을 확인할 수 없으면 그 한계를 설명한다
15. 필요한 정보를 더 묻거나 현재 구성으로 충분하다고 안내하는 것
16. GitHub 로그인
17. GitHub 로그인, 프로젝트 생성·목록·상세·삭제, 입력·추출·분석, Profile 수정·확인 저장, 실패 복구
18. 로그인
19. Profile 수집, Capability, 검증 Catalog, 호환성·중복·충돌 검사, 추천 설명
20. GitHub 로그인만 제공하고 저장소 권한은 요청하지 않는다
21. 본인 프로젝트에만 접근한다
22. 실패 시 재입력 재시도와 직접 작성·수정을 제공한다
23. 내용·대상·환경·선택이 바뀌면 다시 Preview·승인을 받는다

## 잘못된 확정과 확인 부담

최종 Profile의 긍정 값 전체를 대조한 결과, **잘못 포함된 의미는 Codex 외부 연동 1건**이다. 모든 필드가 사용자 확인 전 상태이므로 이를 사용자 확정·DB 저장 오류로 부르지 않는다. 동시에 확인 화면에 잘못된 긍정 제안이 남았다는 문제는 0건으로 처리하지 않는다.

| 항목 | 원문 | 모델·서버·최종 출력 | 최초 잘못된 단계 |
| --- | --- | --- | --- |
| Codex | [L115](E:/AgentFit/output/document-profile-baseline-live-20261002-v1/source.md:115): 초기 지원 Client는 Codex 중심 | C082: external_service / external_integrations / confirmed → 서버 supported → GLM wrongCandidateIds에 미포함 → 최종 external_integrations[1] = Codex | 의미 분류(요청 14). 후속 검토(요청 24)에서도 놓침 |

- 원시 모델 `confirmed`는 66개 후보에서 나왔다. 유효 출력 필드의 긍정 사실로 볼 수 없는 중간 confirmed 의미 10개를 확인했고, 중간 주장 3개는 판정 검토 필요로 남겼다. 이는 최종 Profile의 오확정 1건과 다른 지표다.
- 중간 검토 필요 3개: 부정형 정책 2개(다운로드를 검증 완료로 표시하지 않음, 생성 내용에 Secret·임의 실행 코드를 넣지 않음), GitHub 로그인을 외부 연동의 별칭으로 허용할지 여부. 긍정 채택과 부정 정책 사실을 임의로 합쳐 계수하지 않았다.
- 모델의 negative/confirmed 조합 6회, other/confirmed 조합 7회도 원시 그대로 남겼다. 상태·역할 불일치이며 대부분 보류·제외됐고 그 자체가 최종 13개 오확정을 뜻하지 않는다.
- 사용자 질문은 **필드 질문 10개**와 **미할당 후보 18개를 묶은 질문 1개**다. 일반 승인 질문은 0개이고 10개 필드 질문 모두 REVIEW_ISSUE다. 후보 의미 기준으로 정상 9개가 보류 상태다.
- 보존된 이름/단어가 있다는 이유로 채택한 것으로 간주하지 않았다. React·Node.js·운동 기록을 실제 기술·기능 값으로 출력하지 않았고, Solar Pro 4도 확정 ai 값으로 출력하지 않았다.

## 최초 오류 단계

2개 의미의 대응이 애매하므로 전체 원인 귀속 완료로 표시하지 않는다. 아래는 확인 가능한 최초 불일치의 수이며, 같은 의미를 여러 단계에서 중복 계산하지 않았다.

| 최초 단계 | 정상 의미 수 | 대표 근거 |
| --- | ---: | --- |
| 위치 연결/병합 | 1 | 텍스트 입력: 모델 quote는 맞지만 Mermaid anchor 따옴표 변형으로 연결 탈락 |
| 의미 분류 | 7 | 프로젝트명 역할 오분류, 도메인 other 분류, 환경·권한·템플릿·거부 처리·다운로드 보류 |
| 의미 검토 | 4 | PDF·Markdown 입력 제외, 재접속 유지·정보 부족/후보 없음 처리 제외 |
| 판정 검토 필요 | 2 | 역할·업무 수집의 부분 잔존, Catalog 명사구의 범위 |

관측된 인용 결함은 단계별 후보 사건 기준 **31건**이다: 동작 추출 anchor 불일치 15건, 의미 분류의 인용/등장 순서 오류 12건, 후보를 포함하지 않는 A[·B[ 인용 4건. 이를 기능 누락 31개로 바꾸지 않았다. 같은 의미가 다른 후보로 보존된 경우가 있다.

### 누락 3개

- **F03.03 텍스트 입력**: 원시 동작 응답의 PDF · Markdown · 텍스트 입력은 존재한다. 그러나 anchor의 ASCII 따옴표가 곡선 따옴표로 바뀌어 위치 연결에서 탈락했다. 텍스트 입력을 특정하는 대체 최종 값·확인 후보가 없다. 일반적인 입력이라는 단어만으로 보존 처리하지 않았다.
- **F04.03 확인 결과 저장 및 재접속 후 유지**: 재접속 후 유지라는 필수 완료 결과 C077을 GLM이 not_product_fact로 제외했다. 최종 값에는 저장만 남고 재접속 유지가 빠졌다. 원시 modelDecisions 감사 기록은 남지만 C077은 needs_confirmation 대상이 아니므로 보류 복구로 세지 않았다.
- **F10.04 정보 부족·호환 후보 없음 및 후속 정보 안내**: 정보 부족·호환 후보 없음 처리 C079를 GLM이 not_product_fact로 제외했다. 최종 필요한 정보 확인이라는 일반 문구는 호환 후보가 없는 경우와 후속 안내를 모두 보존하지 않는다. C079는 감사 기록에만 남고 확인 필요 후보로 지정되지 않았다.

## 40개 의미별 원문·출력 근거

아래 후보 ID는 이번 실행에서 새로 생성된 ID다. 모델 입력에 기존 ID나 정답을 주입하지 않았다. 전체 위치·원문 인용·일곱 단계의 판단은 meaning-audit.json과 alignment.json에 저장했다.

| ID / 세부 의미 | 결과 | 원문 근거 | 최종 출력 또는 보류 근거 | 판단 이유 |
| --- | --- | --- | --- | --- |
| P01 AgentFit | 보류 | [L1](E:/AgentFit/output/document-profile-baseline-live-20261002-v1/source.md:1): # AgentFit 프로젝트 기획서 | C000: AgentFit / needs_confirmation<br>C003: AgentFit / needs_confirmation<br>C019: AgentFit / needs_confirmation<br>C051: AgentFit / needs_confirmation<br>C136: AgentFit / needs_confirmation | 원문 제목의 AgentFit은 추출됐으나 이름을 external_service/product_operation으로 지정해 서버가 보류했다. Profile 값은 null이고 modelDecisions의 원문 이름과 확인 필요 판정은 남았다. |
| P02 웹 서비스 | 보존 | [L5](E:/AgentFit/output/document-profile-baseline-live-20261002-v1/source.md:5): > **기획서와 역할에서 출발해 개발환경을 확인하고, 프로젝트에 맞는 AI 설정을 추천·생성·적용 안내하는 웹 서비스** | 웹 서비스 | 원문과 최종 값 모두 웹 서비스다. |
| P03 AI 개발 도구와 설정 | 보류 | [L9](E:/AgentFit/output/document-profile-baseline-live-20261002-v1/source.md:9): AgentFit은 개발 초보자가 자신의 프로젝트에 어떤 AI 개발 도구와 설정이 필요한지 판단하고, 실제로 사용할 준비를 하도록 돕는다. | C005: AI 개발 도구 / needs_confirmation | AI 개발 도구·설정 분야를 other/non_product로 분류했다. 값은 null이지만 AI 개발 도구 후보 C005가 미할당 확인 질문과 원문 위치에 남았다. 도메인 값 복구 완료로는 세지 않는다. |
| P10 ["GitHub"] | 보존 | [L135](E:/AgentFit/output/document-profile-baseline-live-20261002-v1/source.md:135): - **로그인·접근:** GitHub 로그인만 제공하고 저장소 권한은 요청하지 않는다. 본인 프로젝트에만 접근한다. | GitHub | GitHub 로그인 근거와 GitHub 연동 값이 보존됐다. 추가 Codex 값의 오류는 별도 오확정 감사에 포함한다. |
| F01.01 GitHub를 통한 사용자 로그인 | 보존 | [L135](E:/AgentFit/output/document-profile-baseline-live-20261002-v1/source.md:135): - **로그인·접근:** GitHub 로그인만 제공하고 저장소 권한은 요청하지 않는다. 본인 프로젝트에만 접근한다. | GitHub 로그인<br>GitHub 로그인, 프로젝트 생성·목록·상세·삭제, 입력·추출·분석, Profile 수정·확인 저장, 실패 복구<br>GitHub 로그인만 제공하고 저장소 권한은 요청하지 않는다 | GitHub 로그인이라는 사용자 동작이 그대로 남았다. |
| F02.01 개인 프로젝트 생성 | 보존 | [L109](E:/AgentFit/output/document-profile-baseline-live-20261002-v1/source.md:109): \| 1. 프로젝트·문서 분석 \| GitHub 로그인, 프로젝트 생성·목록·상세·삭제, 입력·추출·분석, Profile 수정·확인 저장, 실패 복구 \| 실제 문서를 분석하고 수정·저장한 값이 재접속 후 유지됨 \| | GitHub 로그인, 프로젝트 생성·목록·상세·삭제, 입력·추출·분석, Profile 수정·확인 저장, 실패 복구<br>본인 프로젝트에만 접근한다 | 프로젝트 생성과 본인 프로젝트만 접근한다는 출력을 함께 대조해 개인 프로젝트 생성을 인정했다. |
| F02.02 프로젝트 목록 조회 | 보존 | [L109](E:/AgentFit/output/document-profile-baseline-live-20261002-v1/source.md:109): \| 1. 프로젝트·문서 분석 \| GitHub 로그인, 프로젝트 생성·목록·상세·삭제, 입력·추출·분석, Profile 수정·확인 저장, 실패 복구 \| 실제 문서를 분석하고 수정·저장한 값이 재접속 후 유지됨 \| | GitHub 로그인, 프로젝트 생성·목록·상세·삭제, 입력·추출·분석, Profile 수정·확인 저장, 실패 복구 | 프로젝트 생성·목록·상세·삭제의 목록을 조회 의미로 인정했다. 표현을 목록 조회로 바꾸도록 요구하지 않았다. |
| F02.03 프로젝트 상세 조회 | 보존 | [L109](E:/AgentFit/output/document-profile-baseline-live-20261002-v1/source.md:109): \| 1. 프로젝트·문서 분석 \| GitHub 로그인, 프로젝트 생성·목록·상세·삭제, 입력·추출·분석, Profile 수정·확인 저장, 실패 복구 \| 실제 문서를 분석하고 수정·저장한 값이 재접속 후 유지됨 \| | GitHub 로그인, 프로젝트 생성·목록·상세·삭제, 입력·추출·분석, Profile 수정·확인 저장, 실패 복구 | 프로젝트 상세가 복합 기능 값에 보존됐다. |
| F02.04 프로젝트 삭제 | 보존 | [L109](E:/AgentFit/output/document-profile-baseline-live-20261002-v1/source.md:109): \| 1. 프로젝트·문서 분석 \| GitHub 로그인, 프로젝트 생성·목록·상세·삭제, 입력·추출·분석, Profile 수정·확인 저장, 실패 복구 \| 실제 문서를 분석하고 수정·저장한 값이 재접속 후 유지됨 \| | GitHub 로그인, 프로젝트 생성·목록·상세·삭제, 입력·추출·분석, Profile 수정·확인 저장, 실패 복구 | 프로젝트 삭제가 복합 기능 값에 보존됐다. |
| F03.01 PDF 입력 | 보류 | [L59](E:/AgentFit/output/document-profile-baseline-live-20261002-v1/source.md:59):     A["GitHub 로그인 · 개인 프로젝트 생성"] --> B["PDF · Markdown · 텍스트 입력"]<br>[L136](E:/AgentFit/output/document-profile-baseline-live-20261002-v1/source.md:136): - **입력 한도:** PDF·Markdown 파일 10 MiB = 10,485,760 bytes 이하, PDF 100쪽 이하, 추출·직접 텍스트 100,000 Unicode code points 이하. 공백·줄바꿈을 포함하고 초과분을 자동 절단하지 않는다. | C042: PDF / needs_confirmation<br>C119: PDF / needs_confirmation | PDF 후보 C121은 분류에서 통과했지만 GLM이 insufficient_evidence로 제외했다. C042/C119가 근거 오류로 확인 필요인 채 남아 PDF 입력을 보류로 계수했다. 파일 종류와 동작은 원문 입력 한도·입력 흐름 문맥으로 판단했다. |
| F03.02 Markdown 입력 | 보류 | [L59](E:/AgentFit/output/document-profile-baseline-live-20261002-v1/source.md:59):     A["GitHub 로그인 · 개인 프로젝트 생성"] --> B["PDF · Markdown · 텍스트 입력"]<br>[L136](E:/AgentFit/output/document-profile-baseline-live-20261002-v1/source.md:136): - **입력 한도:** PDF·Markdown 파일 10 MiB = 10,485,760 bytes 이하, PDF 100쪽 이하, 추출·직접 텍스트 100,000 Unicode code points 이하. 공백·줄바꿈을 포함하고 초과분을 자동 절단하지 않는다. | C043: Markdown / needs_confirmation | Markdown 후보 C120을 GLM이 insufficient_evidence로 제외했다. C043의 확인 필요 후보와 위치는 최종 응답에 남았다. |
| F03.03 텍스트 입력 | 누락 | [L59](E:/AgentFit/output/document-profile-baseline-live-20261002-v1/source.md:59):     A["GitHub 로그인 · 개인 프로젝트 생성"] --> B["PDF · Markdown · 텍스트 입력"]<br>[L136](E:/AgentFit/output/document-profile-baseline-live-20261002-v1/source.md:136): - **입력 한도:** PDF·Markdown 파일 10 MiB = 10,485,760 bytes 이하, PDF 100쪽 이하, 추출·직접 텍스트 100,000 Unicode code points 이하. 공백·줄바꿈을 포함하고 초과분을 자동 절단하지 않는다. | 해당 최종 의미 없음 | 원시 동작 응답의 PDF · Markdown · 텍스트 입력은 존재한다. 그러나 anchor의 ASCII 따옴표가 곡선 따옴표로 바뀌어 위치 연결에서 탈락했다. 텍스트 입력을 특정하는 대체 최종 값·확인 후보가 없다. 일반적인 입력이라는 단어만으로 보존 처리하지 않았다. |
| F03.04 문서 내용 추출 | 보존 | [L109](E:/AgentFit/output/document-profile-baseline-live-20261002-v1/source.md:109): \| 1. 프로젝트·문서 분석 \| GitHub 로그인, 프로젝트 생성·목록·상세·삭제, 입력·추출·분석, Profile 수정·확인 저장, 실패 복구 \| 실제 문서를 분석하고 수정·저장한 값이 재접속 후 유지됨 \| | GitHub 로그인, 프로젝트 생성·목록·상세·삭제, 입력·추출·분석, Profile 수정·확인 저장, 실패 복구 | 필수 범위의 입력·추출·분석에서 문서 추출 동작이 남았다. |
| F03.05 Project Profile 분석 초안과 출처·근거 위치 제공 | 보존 | [L46](E:/AgentFit/output/document-profile-baseline-live-20261002-v1/source.md:46): \| 문서 분석 \| 수정 가능한 Project Profile, 미정 항목, 출처·근거 위치 \| | 수정 가능한 Project Profile, 미정 항목, 출처·근거 위치<br>GitHub 로그인, 프로젝트 생성·목록·상세·삭제, 입력·추출·분석, Profile 수정·확인 저장, 실패 복구 | 문서 분석 동작과 수정 가능한 Project Profile·미정 항목·출처·근거 위치를 함께 보존한다. 수정 가능한 분석 결과를 초안 의미로 인정했다. |
| F04.01 Profile 수정 | 보존 | [L61](E:/AgentFit/output/document-profile-baseline-live-20261002-v1/source.md:61):     C --> D["사용자 확인 · 수정 · 저장"] | 수정 가능한 Project Profile, 미정 항목, 출처·근거 위치<br>GitHub 로그인, 프로젝트 생성·목록·상세·삭제, 입력·추출·분석, Profile 수정·확인 저장, 실패 복구 | 수정 가능한 Profile과 Profile 수정이라는 출력이 있다. |
| F04.02 사용자의 Profile 확인 | 보존 | [L61](E:/AgentFit/output/document-profile-baseline-live-20261002-v1/source.md:61):     C --> D["사용자 확인 · 수정 · 저장"] | GitHub 로그인, 프로젝트 생성·목록·상세·삭제, 입력·추출·분석, Profile 수정·확인 저장, 실패 복구 | Profile 수정·확인 저장에 확인 동작이 남았다. |
| F04.03 확인 결과 저장 및 재접속 후 유지 | 누락 | [L109](E:/AgentFit/output/document-profile-baseline-live-20261002-v1/source.md:109): \| 1. 프로젝트·문서 분석 \| GitHub 로그인, 프로젝트 생성·목록·상세·삭제, 입력·추출·분석, Profile 수정·확인 저장, 실패 복구 \| 실제 문서를 분석하고 수정·저장한 값이 재접속 후 유지됨 \| | 해당 최종 의미 없음 | 재접속 후 유지라는 필수 완료 결과 C077을 GLM이 not_product_fact로 제외했다. 최종 값에는 저장만 남고 재접속 유지가 빠졌다. 원시 modelDecisions 감사 기록은 남지만 C077은 needs_confirmation 대상이 아니므로 보류 복구로 세지 않았다. |
| F05.01 실패 후 재입력·재시도 | 보존 | [L138](E:/AgentFit/output/document-profile-baseline-live-20261002-v1/source.md:138): - **복구·보관:** 실패 시 재입력 재시도와 직접 작성·수정을 제공한다. 관리 원문·추출문은 처리 종료 후 보관하지 않고 Profile·최소 문서 정보·분석 시도·감사 기록은 프로젝트 삭제에 연동한다. 외부 AI의 별도 보관 조건은 고지한다. | 실패 시 재입력 재시도와 직접 작성·수정을 제공한다 | 실패 시 재입력 재시도를 제공한다는 출력이 있다. |
| F05.02 분석 실패 후 직접 작성·수정 | 보존 | [L138](E:/AgentFit/output/document-profile-baseline-live-20261002-v1/source.md:138): - **복구·보관:** 실패 시 재입력 재시도와 직접 작성·수정을 제공한다. 관리 원문·추출문은 처리 종료 후 보관하지 않고 Profile·최소 문서 정보·분석 시도·감사 기록은 프로젝트 삭제에 연동한다. 외부 AI의 별도 보관 조건은 고지한다. | 실패 시 재입력 재시도와 직접 작성·수정을 제공한다 | 실패 시 직접 작성·수정을 제공한다는 출력이 있다. |
| F06.01 사용자 역할·업무 정보 수집 | 사람 검토 필요 | [L64](E:/AgentFit/output/document-profile-baseline-live-20261002-v1/source.md:64):     D --> F["역할 · 업무 · 개발환경 확인"]<br>[L96](E:/AgentFit/output/document-profile-baseline-live-20261002-v1/source.md:96): \| Developer Profile \| 사용자의 역할·주요 업무·개발 경험 \| | Profile 수집, Capability, 검증 Catalog, 호환성·중복·충돌 검사, 추천 설명<br>C006: 기획서를 넣고 분석 결과를 확인한 뒤 자신의 역할과 개발환경을 알려준다 / needs_confirmation | 검토에서 역할·실제 업무 입력 C055가 제외됐다. 최종 Profile 수집과 보류 후보 C006의 역할 입력이 주요 업무 수집까지 충분히 보존하는지는 애매하다. 성공이나 누락으로 강제 판정하지 않고 사람 검토 필요로 남겼다. |
| F06.02 개발환경 정보 확인 | 보류 | [L64](E:/AgentFit/output/document-profile-baseline-live-20261002-v1/source.md:64):     D --> F["역할 · 업무 · 개발환경 확인"]<br>[L97](E:/AgentFit/output/document-profile-baseline-live-20261002-v1/source.md:97): \| Environment Profile \| OS·AI Client·런타임·기존 구성·인증 준비와 확인 출처 \| | C006: 기획서를 넣고 분석 결과를 확인한 뒤 자신의 역할과 개발환경을 알려준다 / needs_confirmation | 개발환경을 알려준다는 C006이 확인 필요로 남았다. 최종 값의 현재 조건 정리만으로 환경 정보 수집이 명확하다고 보지 않았다. |
| F07.01 업무에 필요한 작업 능력 도출 | 보존 | [L65](E:/AgentFit/output/document-profile-baseline-live-20261002-v1/source.md:65):     F --> G["필요한 Capability 도출 · Catalog 검토"] | 문서를 구조화하고 역할에 필요한 작업 능력을 정리 | 역할에 필요한 작업 능력을 정리한다는 출력으로 업무 능력 도출을 보존한다. |
| F08.01 검증된 도구와 지원 조건을 담은 Catalog 검토 | 사람 검토 필요 | [L65](E:/AgentFit/output/document-profile-baseline-live-20261002-v1/source.md:65):     F --> G["필요한 Capability 도출 · Catalog 검토"]<br>[L99](E:/AgentFit/output/document-profile-baseline-live-20261002-v1/source.md:99): \| Catalog \| 팀이 검증한 도구와 지원 조건을 관리하는 목록 \| | Profile 수집, Capability, 검증 Catalog, 호환성·중복·충돌 검사, 추천 설명 | 원시 응답에는 Catalog 검토가 있지만 위치 연결 후에는 검증 Catalog라는 명사구가 주로 남았다. 지원 조건을 담은 도구 목록을 검토한다는 세부 의미까지 포함하는지 판단을 보류한다. Catalog라는 단어의 존재만으로 통과시키지 않았다. |
| F09.01 호환성 검사 | 보존 | [L110](E:/AgentFit/output/document-profile-baseline-live-20261002-v1/source.md:110): \| 2. 역할·환경·추천 \| Profile 수집, Capability, 검증 Catalog, 호환성·중복·충돌 검사, 추천 설명 \| 서로 다른 업무·환경에 맞는 결과와 추가 불필요·정보 부족·후보 없음 처리 \| | 호환 조건·중복·충돌·추가 준비를 확인<br>Profile 수집, Capability, 검증 Catalog, 호환성·중복·충돌 검사, 추천 설명 | 호환 조건 확인과 호환성 검사가 보존됐다. |
| F09.02 중복 검사 | 보존 | [L110](E:/AgentFit/output/document-profile-baseline-live-20261002-v1/source.md:110): \| 2. 역할·환경·추천 \| Profile 수집, Capability, 검증 Catalog, 호환성·중복·충돌 검사, 추천 설명 \| 서로 다른 업무·환경에 맞는 결과와 추가 불필요·정보 부족·후보 없음 처리 \| | 호환 조건·중복·충돌·추가 준비를 확인<br>Profile 수집, Capability, 검증 Catalog, 호환성·중복·충돌 검사, 추천 설명 | 중복 확인·검사가 보존됐다. |
| F09.03 충돌 검사 | 보존 | [L110](E:/AgentFit/output/document-profile-baseline-live-20261002-v1/source.md:110): \| 2. 역할·환경·추천 \| Profile 수집, Capability, 검증 Catalog, 호환성·중복·충돌 검사, 추천 설명 \| 서로 다른 업무·환경에 맞는 결과와 추가 불필요·정보 부족·후보 없음 처리 \| | 호환 조건·중복·충돌·추가 준비를 확인<br>Profile 수집, Capability, 검증 Catalog, 호환성·중복·충돌 검사, 추천 설명 | 충돌 확인·검사가 보존됐다. |
| F10.01 적합한 최소 구성 추천 | 보존 | [L48](E:/AgentFit/output/document-profile-baseline-live-20261002-v1/source.md:48): \| 추천 \| 필요한 최소 구성, 이유·조건·권한 또는 추가 도구 불필요 판단 \| | 현재 조건에 맞는 최소 구성을 제안한다<br>필요한 최소 구성, 이유·조건·권한 또는 추가 도구 불필요 판단 | 현재 조건에 맞는 최소 구성 제안이 보존됐다. |
| F10.02 추천 이유·조건·권한 설명 | 보존 | [L48](E:/AgentFit/output/document-profile-baseline-live-20261002-v1/source.md:48): \| 추천 \| 필요한 최소 구성, 이유·조건·권한 또는 추가 도구 불필요 판단 \| | 추천 이유·권한·바뀔 내용을 확인하고 승인한 설정과 적용 안내를 받는다<br>필요한 최소 구성, 이유·조건·권한 또는 추가 도구 불필요 판단 | 추천 이유·조건·권한을 사용자에게 제공하는 의미가 보존됐다. |
| F10.03 추가 도구 불필요 및 현재 구성 안내 | 보존 | [L67](E:/AgentFit/output/document-profile-baseline-live-20261002-v1/source.md:67):     G --> I["추가 도구 불필요"]<br>[L72](E:/AgentFit/output/document-profile-baseline-live-20261002-v1/source.md:72):     I --> N["현재 구성으로 할 수 있는 작업 안내"] | 필요한 최소 구성, 이유·조건·권한 또는 추가 도구 불필요 판단<br>필요한 정보를 더 묻거나 현재 구성으로 충분하다고 안내하는 것 | 추가 도구 불필요 판단과 현재 구성으로 충분하다는 안내가 함께 보존됐다. |
| F10.04 정보 부족·호환 후보 없음 및 후속 정보 안내 | 누락 | [L68](E:/AgentFit/output/document-profile-baseline-live-20261002-v1/source.md:68):     G --> J["정보 확인 필요 · 호환 후보 없음"]<br>[L73](E:/AgentFit/output/document-profile-baseline-live-20261002-v1/source.md:73):     J --> O["필요 정보 또는 미지원 조건 안내"] | 해당 최종 의미 없음 | 정보 부족·호환 후보 없음 처리 C079를 GLM이 not_product_fact로 제외했다. 최종 필요한 정보 확인이라는 일반 문구는 호환 후보가 없는 경우와 후속 안내를 모두 보존하지 않는다. C079는 감사 기록에만 남고 확인 필요 후보로 지정되지 않았다. |
| F11.01 지원 권한 선택과 확인 | 보류 | [L69](E:/AgentFit/output/document-profile-baseline-live-20261002-v1/source.md:69):     H --> K["구성 선택 · 권한 확인"] | C080: 지원 권한 선택, 검증 템플릿, Preview·최종 승인, 다운로드·적용·인증·확인 안내 / needs_confirmation<br>C064: 사용자가 선택·권한·설정 내용을 승인하면 파일과 적용 안내를 제공한다 / needs_confirmation | 권한 확인은 최종 값에 있으나 지원 권한 선택을 담은 C080/C064는 external_service로 오분류되어 확인 필요로 남았다. 선택·확인 전체 의미는 보류다. |
| F12.01 검증 템플릿을 이용한 승인 내용과 일치하는 설정 파일 생성 | 보류 | [L50](E:/AgentFit/output/document-profile-baseline-live-20261002-v1/source.md:50): \| 승인·다운로드 \| 승인 내용과 일치하는 설정 파일, 적용·인증·무해한 사용 확인 안내 \|<br>[L111](E:/AgentFit/output/document-profile-baseline-live-20261002-v1/source.md:111): \| 3. 권한·설정·다운로드 \| 지원 권한 선택, 검증 템플릿, Preview·최종 승인, 다운로드·적용·인증·확인 안내 \| 승인과 산출물 일치, 거부·취소·충돌 처리, 지원 과제의 실제 사용 평가 \| | 승인 내용과 일치하는 설정 파일, 적용·인증·무해한 사용 확인 안내<br>C080: 지원 권한 선택, 검증 템플릿, Preview·최종 승인, 다운로드·적용·인증·확인 안내 / needs_confirmation | 승인 내용과 일치하는 설정 파일은 남았으나 검증 템플릿은 C080의 보류 후보에만 있다. 일부 내용만으로 전체 의미를 보존 처리하지 않았다. |
| F13.01 대상 경로·내용·변경안과 충돌 정보 Preview | 보존 | [L49](E:/AgentFit/output/document-profile-baseline-live-20261002-v1/source.md:49): \| 설정 검토 \| 대상 경로·설정 내용·확인 범위에 맞는 변경안과 충돌 정보 \|<br>[L141](E:/AgentFit/output/document-profile-baseline-live-20261002-v1/source.md:141): - **설정·승인:** 기존 설정 미확인 시 신규 설정안으로 표시한다. 내용·대상·환경·선택이 바뀌면 다시 Preview·승인을 받는다. Secret과 임의 실행 코드는 생성 내용에 넣지 않는다. | 대상 경로·설정 내용·확인 범위에 맞는 변경안과 충돌 정보<br>내용·대상·환경·선택이 바뀌면 다시 Preview·승인을 받는다 | 대상 경로·설정 내용·변경안·충돌 정보와 Preview 재검토 동작을 함께 대조했다. 설정 검토 결과가 실제 변경안을 보여주는 의미를 보존한다. |
| F13.02 최종 승인 및 변경 시 재승인 | 보존 | [L70](E:/AgentFit/output/document-profile-baseline-live-20261002-v1/source.md:70):     K --> L["설정 Preview · 최종 승인"]<br>[L141](E:/AgentFit/output/document-profile-baseline-live-20261002-v1/source.md:141): - **설정·승인:** 기존 설정 미확인 시 신규 설정안으로 표시한다. 내용·대상·환경·선택이 바뀌면 다시 Preview·승인을 받는다. Secret과 임의 실행 코드는 생성 내용에 넣지 않는다. | 추천 이유·권한·바뀔 내용을 확인하고 승인한 설정과 적용 안내를 받는다<br>내용·대상·환경·선택이 바뀌면 다시 Preview·승인을 받는다 | 승인한 설정을 받는 흐름과 내용·대상·환경·선택 변경 시 다시 Preview·승인을 받는 동작이 남았다. |
| F13.03 권한·설정의 거부·취소·충돌 처리 | 보류 | [L111](E:/AgentFit/output/document-profile-baseline-live-20261002-v1/source.md:111): \| 3. 권한·설정·다운로드 \| 지원 권한 선택, 검증 템플릿, Preview·최종 승인, 다운로드·적용·인증·확인 안내 \| 승인과 산출물 일치, 거부·취소·충돌 처리, 지원 과제의 실제 사용 평가 \| | C081: 승인과 산출물 일치, 거부·취소·충돌 처리, 지원 과제의 실제 사용 평가 / needs_confirmation | 거부·취소·충돌 처리 C081이 external_service로 분류되어 확인 필요로 남았다. 최종 단순 충돌 정보와 동일하게 보지 않았다. |
| F14.01 승인한 설정 파일 다운로드 | 보류 | [L50](E:/AgentFit/output/document-profile-baseline-live-20261002-v1/source.md:50): \| 승인·다운로드 \| 승인 내용과 일치하는 설정 파일, 적용·인증·무해한 사용 확인 안내 \|<br>[L71](E:/AgentFit/output/document-profile-baseline-live-20261002-v1/source.md:71):     L --> M["다운로드 · 적용 · 인증 · 사용 확인 안내"] | C080: 지원 권한 선택, 검증 템플릿, Preview·최종 승인, 다운로드·적용·인증·확인 안내 / needs_confirmation | 승인과 산출물의 일치는 남았으나 다운로드 동작을 담은 C080은 확인 필요다. 설정 파일 제공과 다운로드를 임의로 동일시하지 않았다. |
| F15.01 설정 적용 안내 | 보존 | [L50](E:/AgentFit/output/document-profile-baseline-live-20261002-v1/source.md:50): \| 승인·다운로드 \| 승인 내용과 일치하는 설정 파일, 적용·인증·무해한 사용 확인 안내 \| | 변경 내용, 인증과 적용 방법, 실패 시 다음 행동 안내<br>승인 내용과 일치하는 설정 파일, 적용·인증·무해한 사용 확인 안내 | 설정 적용 방법·안내가 보존됐다. |
| F15.02 인증 준비 안내 | 보존 | [L50](E:/AgentFit/output/document-profile-baseline-live-20261002-v1/source.md:50): \| 승인·다운로드 \| 승인 내용과 일치하는 설정 파일, 적용·인증·무해한 사용 확인 안내 \| | 변경 내용, 인증과 적용 방법, 실패 시 다음 행동 안내<br>승인 내용과 일치하는 설정 파일, 적용·인증·무해한 사용 확인 안내 | 인증 준비·방법 안내가 보존됐다. |
| F15.03 무해한 실제 사용 확인 안내 | 보존 | [L50](E:/AgentFit/output/document-profile-baseline-live-20261002-v1/source.md:50): \| 승인·다운로드 \| 승인 내용과 일치하는 설정 파일, 적용·인증·무해한 사용 확인 안내 \| | 승인 내용과 일치하는 설정 파일, 적용·인증·무해한 사용 확인 안내 | 무해한 사용 확인 안내라는 구체 조건이 남았다. |
| F16.01 확인 주체·범위·버전에 따른 상태 표시 | 보존 | [L51](E:/AgentFit/output/document-profile-baseline-live-20261002-v1/source.md:51): \| 상태 확인 \| 누가 어떤 범위와 버전을 확인했는지에 따른 상태 \| | 누가 어떤 범위와 버전을 확인했는지에 따른 상태 | 확인 주체·범위·버전에 따른 상태가 그대로 남았다. |

## 검증·제약과 종료 상태

- 로컬 실행 제한 테스트 4건 통과: 50회 차단, 남은 시간 축소, 첫 실패 후 추가 전송 차단, 허용 모델 외 전송 차단. 실제 평가 호출은 이 25회 한 번뿐이다.
- 실행 후 원문·골드·분석 코드·지침·스키마 해시, 원문 위치, 모델·요청 수·시간 상한을 확인했다. trace 관측 오류 0건. 의미 대응표는 해당 trace와 gold 해시에 묶여 있다.
- 의미 판단은 저장 자료를 직접 읽은 수동 대조다. 별도 모델 채점 호출을 사용하지 않았으며 출력의 애매한 두 의미는 사람 검토 필요로 남겼다.
- 기존 채점기는 중간 모델 주장 3개의 판정을 보류하면 통합 claimAuditComplete와 모델/서버 오확정 집계가 완료되지 않도록 한다. 이를 수정하지 않았다. 위 최종 Profile 1건은 audit-summary.json의 별도 최종 값 전수 감사 결과이며, 중간 모델의 미결 판정과 섞지 않았다. 전체 metrics.complete도 false다.
- 운영 HTTP 배포 설정·사용자 확인 UI·실제 Spring 저장은 이번 평가로 검증하지 않았다. 현재 worker/부모 응답 검증 경로를 실행했으며, 실제 HTTP 진입점과의 동일성은 앞선 합성 테스트 근거다.
- 이 문서는 기존 개발에 사용됐으므로 새 기획서에 대한 일반화 성능을 입증하지 않는다. 1회 결과이며 성공률 추정치가 아니다.
- 자동 수정·추가 실험·서비스 적용을 하지 않고 종료한다. 큰 goal은 중단 상태를 유지한다.

## 저장 자료

- [코드·원문·정답·제한 동결](E:/AgentFit/output/document-profile-baseline-live-20261002-v1/freeze.json)
- [실제 요청 수·시간](E:/AgentFit/output/document-profile-baseline-live-20261002-v1/execution.json)
- [요청별 제한·상태](E:/AgentFit/output/document-profile-baseline-live-20261002-v1/request-journal.json)
- [실제 최종 응답](E:/AgentFit/output/document-profile-baseline-live-20261002-v1/result.json)
- [전체 단계·요청·응답](E:/AgentFit/output/document-profile-baseline-live-20261002-v1/trace.json)
- [기존 채점기 입력](E:/AgentFit/output/document-profile-baseline-live-20261002-v1/alignment.json)
- [40개 의미의 수동 근거](E:/AgentFit/output/document-profile-baseline-live-20261002-v1/meaning-audit.json)
- [별도 감사 요약](E:/AgentFit/output/document-profile-baseline-live-20261002-v1/audit-summary.json)
- [기존 채점기 결과](E:/AgentFit/output/document-profile-baseline-live-20261002-v1/metrics.json)

## 중간 confirmed 상태 감사의 확인된 10개 의미

유효 출력 필드의 긍정 사실에 해당하는지를 검사한 상태 정합성 감사다. 최종 긍정 값 오류 1건과 합산하지 않는다.

| 의미 | 기대 상태 | 원시 confirmed 횟수 | 최종 긍정 값 횟수 | 근거 |
| --- | --- | ---: | ---: | --- |
| features: 팀 공유 | explicit_none | 2 | 0 | 첫 기능에서 명시적으로 제외한 기능이다. negative 축을 기록했지만 confirmed 상태가 함께 나왔다. |
| other: OS | out_of_scope | 1 | 0 | 출력 필드가 other인 문서 용어·환경 종류·개발 절차이며 유효 출력 필드의 긍정 사실로 확정할 수 없다. |
| other: AI | out_of_scope | 1 | 0 | 출력 필드가 other인 문서 용어·환경 종류·개발 절차이며 유효 출력 필드의 긍정 사실로 확정할 수 없다. |
| other: AI Client | out_of_scope | 1 | 0 | 출력 필드가 other인 문서 용어·환경 종류·개발 절차이며 유효 출력 필드의 긍정 사실로 확정할 수 없다. |
| external_integrations: Codex | out_of_scope | 1 | 1 | Codex는 지원 Client다. 이번 원문은 제품이 연동하는 외부 서비스 채택을 확정하지 않는다. |
| features: 여러 문서 병합 | explicit_none | 1 | 0 | 첫 기능에서 명시적으로 제외한 기능이다. negative 축을 기록했지만 confirmed 상태가 함께 나왔다. |
| other: 검증 실행 계획 | out_of_scope | 1 | 0 | 출력 필드가 other인 문서 용어·환경 종류·개발 절차이며 유효 출력 필드의 긍정 사실로 확정할 수 없다. |
| other: 공통 PRD | out_of_scope | 1 | 0 | 출력 필드가 other인 문서 용어·환경 종류·개발 절차이며 유효 출력 필드의 긍정 사실로 확정할 수 없다. |
| other: 애플리케이션 소스·설정·테스트 작성과 패키지 설치는 작업 범위를 제시하고 구현 승인을 받은 뒤 진행한다 | out_of_scope | 1 | 0 | 출력 필드가 other인 문서 용어·환경 종류·개발 절차이며 유효 출력 필드의 긍정 사실로 확정할 수 없다. |
| other: 배포 | out_of_scope | 1 | 0 | 출력 필드가 other인 문서 용어·환경 종류·개발 절차이며 유효 출력 필드의 긍정 사실로 확정할 수 없다. |
