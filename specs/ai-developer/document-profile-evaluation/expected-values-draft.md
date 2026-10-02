# AgentFit 기획서 — 10개 Profile 필드 기대값 초안

**상태: 사용자 검토 전 초안. 실제 모델 결과가 아님.**

**2026-10-02 갱신:** 사용자가 이 기대값을 기준으로 로컬 평가 준비를 진행하도록 승인했다. 아래 초안 내용은 변경하지 않았으며 승인·해시는 [baseline-contract.json](baseline-contract.json)에 기록했다. 실제 모델 결과는 아직 없다.

- 원문: [project-proposal.md](E:/AgentFit/Docs/project-proposal.md), 2026-09-08판, 전체 186줄.
- 원본 바이트 SHA-256: `9c0115a34e4ae90f905c3021569bc4b5c10284388c7bac264b76e2d3d077f451`. UTF-8, CRLF 유지, 7796 Unicode code points.
- 기존 개발 문서이므로 일반화 검증용 새 문서가 아니다. 연결 문서·대화의 스택 정보는 사용하지 않는다.
- 범위: 이번 학기 필수 제품 요구. 아직 구현하지 않은 필수 요구도 문서의 긍정 사실이며, 구현 완료와 구분한다.
- 명시됨 / 미정 / 명시적 없음은 정답의 사실 상태다. 모델의 confirmed와 사용자가 직접 승인한 상태를 동일시하지 않는다.

## 1. 열 개 필드

| 필드 | 기대 상태·값 | 판단 근거 |
| --- | --- | --- |
| `project_name` | 명시됨 — "AgentFit" | 대상 프로젝트 이름 [L1](E:/AgentFit/Docs/project-proposal.md:1) · [L9](E:/AgentFit/Docs/project-proposal.md:9) |
| `project_type` | 명시됨 — "웹 서비스" | 사용자에게 제공할 서비스 형태 [L5](E:/AgentFit/Docs/project-proposal.md:5) · [L163](E:/AgentFit/Docs/project-proposal.md:163) |
| `domain` | 명시됨 — "AI 개발 도구와 설정" | 개발 초보자의 AI 개발 도구 선택·설정 지원 문제 영역. 역할 이름이나 특정 모델명과 구분. [L9](E:/AgentFit/Docs/project-proposal.md:9) · [L31](E:/AgentFit/Docs/project-proposal.md:31) |
| `frontend` | 미정 (`null`) | 대상 AgentFit의 프런트엔드 스택은 미기재. React는 가상 운동 기록 서비스의 예시. [L80](E:/AgentFit/Docs/project-proposal.md:80) · [L89](E:/AgentFit/Docs/project-proposal.md:89) · [L163](E:/AgentFit/Docs/project-proposal.md:163) |
| `backend` | 미정 (`null`) | 대상 백엔드 스택은 미기재. Node.js는 다른 프로젝트 예시이고 Modular Monolith는 아키텍처. [L80](E:/AgentFit/Docs/project-proposal.md:80) · [L89](E:/AgentFit/Docs/project-proposal.md:89) · [L163](E:/AgentFit/Docs/project-proposal.md:163) |
| `ai` | 미정 (`null`) | 운영 Provider 채택은 평가 후 결정. Solar Pro 4는 평가 후보, Codex는 지원 Client. [L115](E:/AgentFit/Docs/project-proposal.md:115) |
| `database` | 미정 (`null`) | DB 사용 방향은 있으나 제품·엔진은 미기재. DB 없음으로 판단할 근거는 없음. [L163](E:/AgentFit/Docs/project-proposal.md:163) |
| `deployment` | 미정 (`null`) | 전체 186줄에서 대상 프로젝트의 구체적 배포 환경을 찾지 못함. 예시 프로젝트의 배포 미정 문구를 대상의 명시적 선언으로 사용하지 않음. [L80](E:/AgentFit/Docs/project-proposal.md:80) · [L89](E:/AgentFit/Docs/project-proposal.md:89) · [L163](E:/AgentFit/Docs/project-proposal.md:163) |
| `features` | 명시됨 — 대표 기능 16묶음(아래) | 대표 기능 16묶음. 표현·분할 방식이 아니라 아래 의미 단위의 보존을 검토. [L46](E:/AgentFit/Docs/project-proposal.md:46) · [L47](E:/AgentFit/Docs/project-proposal.md:47) · [L48](E:/AgentFit/Docs/project-proposal.md:48) · [L49](E:/AgentFit/Docs/project-proposal.md:49) · [L50](E:/AgentFit/Docs/project-proposal.md:50) · [L51](E:/AgentFit/Docs/project-proposal.md:51) · [L109](E:/AgentFit/Docs/project-proposal.md:109) · [L110](E:/AgentFit/Docs/project-proposal.md:110) · [L111](E:/AgentFit/Docs/project-proposal.md:111) |
| `external_integrations` | 명시됨 — ["GitHub"] | 실제 외부 로그인 서비스. 저장소 접근 권한을 요청한다는 뜻은 아님. [L59](E:/AgentFit/Docs/project-proposal.md:59) · [L109](E:/AgentFit/Docs/project-proposal.md:109) · [L135](E:/AgentFit/Docs/project-proposal.md:135) |

**필드 전체 기준: 명시됨 5개 / 미정 5개 / 명시적 없음 0개.** 이 문서에 없는 ‘필드 전체가 없음’ 정답을 만들지 않는다. DB 사용 방향은 있으나 DB 제품은 미정이다.

미정 필드의 아래 문맥은 평가자 설명용이다. 공개 Profile에서는 `data=null`, `sources=UNKNOWN`, `evidence=[]`이며 해당 이름을 `unknownFields`에 넣는다. 기술을 안 쓴다는 의미의 빈 배열로 바꾸지 않는다.

### 핵심 원문 인용

[L1](E:/AgentFit/Docs/project-proposal.md:1)

> # AgentFit 프로젝트 기획서

[L5](E:/AgentFit/Docs/project-proposal.md:5)

> > **기획서와 역할에서 출발해 개발환경을 확인하고, 프로젝트에 맞는 AI 설정을 추천·생성·적용 안내하는 웹 서비스**

[L9](E:/AgentFit/Docs/project-proposal.md:9)

> AgentFit은 개발 초보자가 자신의 프로젝트에 어떤 AI 개발 도구와 설정이 필요한지 판단하고, 실제로 사용할 준비를 하도록 돕는다.

[L80](E:/AgentFit/Docs/project-proposal.md:80)

> 가상의 운동 기록 서비스 기획서에 React·Node.js·로그인·운동 기록 기능이 있고 DB와 배포는 정해져 있지 않다고 하자.

[L89](E:/AgentFit/Docs/project-proposal.md:89)

> 위 기술과 역할은 설명용 예시이며 유일한 지원 대상으로 제한하지 않는다. 특정 도구의 추천·호환성이 검증됐다는 예시도 아니다.

[L115](E:/AgentFit/Docs/project-proposal.md:115)

> 초기 지원 Client는 Codex 중심이며 Catalog는 팀이 검증한 약 15~20개 도구를 목표로 한다. 정확한 도구·OS·Client 버전·지원 조합은 해당 Feature에서 검증해 확정한다. 문서 분석에는 Solar Pro 4를 먼저 평가하며 운영 Provider 채택은 실제 품질 검증 후 결정한다.

[L135](E:/AgentFit/Docs/project-proposal.md:135)

> - **로그인·접근:** GitHub 로그인만 제공하고 저장소 권한은 요청하지 않는다. 본인 프로젝트에만 접근한다.

[L163](E:/AgentFit/Docs/project-proposal.md:163)

> 단일 웹 서비스와 DB를 중심으로 모듈을 나누는 Modular Monolith를 우선한다. 정확한 스택·버전·API·DB·파일 구조는 공통 기술 계획에서 관리한다.

## 2. 대표 기능과 세부 의미

기능 배열의 정답 문자열·순서·분할 개수를 강제하지 않는다. 아래 16묶음에 포함된 세부 의미를 보존하고 원문에 근거해야 한다. 제목만 넓게 붙여 누락을 감추는 요약은 인정하지 않는다. 동일 의미의 중복 언급은 한 번 센다.

| ID | 대표 표현 | 보존할 의미 | 근거 |
| --- | --- | --- | --- |
| F01 | GitHub 로그인 | GitHub를 통한 사용자 로그인 | [L109](E:/AgentFit/Docs/project-proposal.md:109) · [L135](E:/AgentFit/Docs/project-proposal.md:135) |
| F02 | 프로젝트 생성·목록·상세·삭제 | 개인 프로젝트 생성 / 프로젝트 목록 조회 / 프로젝트 상세 조회 / 프로젝트 삭제 | [L109](E:/AgentFit/Docs/project-proposal.md:109) |
| F03 | 입력·추출·분석 | PDF 입력 / Markdown 입력 / 텍스트 입력 / 문서 내용 추출 / Project Profile 분석 초안과 출처·근거 위치 제공 | [L46](E:/AgentFit/Docs/project-proposal.md:46) · [L59](E:/AgentFit/Docs/project-proposal.md:59) · [L60](E:/AgentFit/Docs/project-proposal.md:60) · [L109](E:/AgentFit/Docs/project-proposal.md:109) · [L136](E:/AgentFit/Docs/project-proposal.md:136) |
| F04 | Profile 수정·확인 저장 | Profile 수정 / 사용자의 Profile 확인 / 확인 결과 저장 및 재접속 후 유지 | [L61](E:/AgentFit/Docs/project-proposal.md:61) · [L109](E:/AgentFit/Docs/project-proposal.md:109) · [L137](E:/AgentFit/Docs/project-proposal.md:137) |
| F05 | 실패 복구 | 실패 후 재입력·재시도 / 분석 실패 후 직접 작성·수정 | [L62](E:/AgentFit/Docs/project-proposal.md:62) · [L109](E:/AgentFit/Docs/project-proposal.md:109) · [L138](E:/AgentFit/Docs/project-proposal.md:138) |
| F06 | 역할·환경 확인 | 사용자 역할·업무 정보 수집 / 개발환경 정보 확인 | [L47](E:/AgentFit/Docs/project-proposal.md:47) · [L64](E:/AgentFit/Docs/project-proposal.md:64) · [L110](E:/AgentFit/Docs/project-proposal.md:110) |
| F07 | 필요한 Capability 도출 | 업무에 필요한 작업 능력 도출 | [L65](E:/AgentFit/Docs/project-proposal.md:65) · [L110](E:/AgentFit/Docs/project-proposal.md:110) |
| F08 | Catalog 검토 | 검증된 도구와 지원 조건을 담은 Catalog 검토 | [L65](E:/AgentFit/Docs/project-proposal.md:65) · [L99](E:/AgentFit/Docs/project-proposal.md:99) · [L110](E:/AgentFit/Docs/project-proposal.md:110) |
| F09 | 호환성·중복·충돌 검사 | 호환성 검사 / 중복 검사 / 충돌 검사 | [L49](E:/AgentFit/Docs/project-proposal.md:49) · [L110](E:/AgentFit/Docs/project-proposal.md:110) |
| F10 | 추천 설명 | 적합한 최소 구성 추천 / 추천 이유·조건·권한 설명 / 추가 도구 불필요 및 현재 구성 안내 / 정보 부족·호환 후보 없음 및 후속 정보 안내 | [L48](E:/AgentFit/Docs/project-proposal.md:48) · [L66](E:/AgentFit/Docs/project-proposal.md:66) · [L67](E:/AgentFit/Docs/project-proposal.md:67) · [L68](E:/AgentFit/Docs/project-proposal.md:68) · [L72](E:/AgentFit/Docs/project-proposal.md:72) · [L73](E:/AgentFit/Docs/project-proposal.md:73) · [L110](E:/AgentFit/Docs/project-proposal.md:110) |
| F11 | 지원 권한 선택 | 지원 권한 선택과 확인 | [L69](E:/AgentFit/Docs/project-proposal.md:69) · [L111](E:/AgentFit/Docs/project-proposal.md:111) |
| F12 | 설정 파일 | 검증 템플릿을 이용한 승인 내용과 일치하는 설정 파일 생성 | [L5](E:/AgentFit/Docs/project-proposal.md:5) · [L50](E:/AgentFit/Docs/project-proposal.md:50) · [L101](E:/AgentFit/Docs/project-proposal.md:101) · [L111](E:/AgentFit/Docs/project-proposal.md:111) |
| F13 | Preview·최종 승인 | 대상 경로·내용·변경안과 충돌 정보 Preview / 최종 승인 및 변경 시 재승인 / 권한·설정의 거부·취소·충돌 처리 | [L49](E:/AgentFit/Docs/project-proposal.md:49) · [L70](E:/AgentFit/Docs/project-proposal.md:70) · [L111](E:/AgentFit/Docs/project-proposal.md:111) · [L141](E:/AgentFit/Docs/project-proposal.md:141) |
| F14 | 다운로드 | 승인한 설정 파일 다운로드 | [L50](E:/AgentFit/Docs/project-proposal.md:50) · [L71](E:/AgentFit/Docs/project-proposal.md:71) · [L111](E:/AgentFit/Docs/project-proposal.md:111) |
| F15 | 적용·인증·확인 안내 | 설정 적용 안내 / 인증 준비 안내 / 무해한 실제 사용 확인 안내 | [L50](E:/AgentFit/Docs/project-proposal.md:50) · [L71](E:/AgentFit/Docs/project-proposal.md:71) · [L111](E:/AgentFit/Docs/project-proposal.md:111) |
| F16 | 상태 확인 | 확인 주체·범위·버전에 따른 상태 표시 | [L51](E:/AgentFit/Docs/project-proposal.md:51) · [L53](E:/AgentFit/Docs/project-proposal.md:53) |

세부 기능 의미 단위는 **36개**, 기능 외 긍정 사실은 **4개**다. 모델이 실제로 출력한 문구와 근거를 보고 각각 대응표를 작성한다. 공개 Profile은 대표 기능 30개 이하를 유지한다.

## 3. 부정·선택 사항·다른 프로젝트 문맥

| ID | 대상 | 기대 상태·범위 | 이유·근거 |
| --- | --- | --- | --- |
| N01 | OCR | explicit_none / 첫 기능 | 첫 기능에서 명시적으로 제외. [L117](E:/AgentFit/Docs/project-proposal.md:117) |
| N02 | 이미지/표의 시각적 의미 해석 | explicit_none / 첫 기능 | 첫 기능에서 명시적으로 제외. [L117](E:/AgentFit/Docs/project-proposal.md:117) |
| N03 | 여러 문서 병합 | explicit_none / 첫 기능 | 첫 기능에서 명시적으로 제외. [L117](E:/AgentFit/Docs/project-proposal.md:117) |
| N04 | 팀 공유 | explicit_none / 첫 기능 | 첫 기능은 개인 소유이며 팀 공유를 포함하지 않음. [L40](E:/AgentFit/Docs/project-proposal.md:40) · [L117](E:/AgentFit/Docs/project-proposal.md:117) |
| N05 | 저장소 권한 요청 | explicit_none / 로그인·접근 정책 | GitHub 로그인과 별개인 권한 범위의 명시적 부정. [L135](E:/AgentFit/Docs/project-proposal.md:135) |
| U01 | 브라우저에서 사용자가 고른 폴더에 적용 | unknown / 선택 확장 | 선택 확장이므로 확정 필수 기능에 합치지 않음. 후보가 있다면 선택 사항의 근거를 보존. [L117](E:/AgentFit/Docs/project-proposal.md:117) |
| U02 | Local CLI | unknown / MVP 비필수 | MVP 필수 아님은 영구적 부재나 채택 선언이 아님. [L117](E:/AgentFit/Docs/project-proposal.md:117) |
| U03 | 모든 AI Client 지원 | unknown / MVP 비필수 | MVP 필수 아님은 영구적 부재나 채택 선언이 아님. [L117](E:/AgentFit/Docs/project-proposal.md:117) |
| U04 | Shell 자동 실행 | unknown / MVP 비필수 | MVP 필수 아님은 영구적 부재나 채택 선언이 아님. [L117](E:/AgentFit/Docs/project-proposal.md:117) |
| U05 | 인터넷 전체 도구의 실시간 자동 설치 | unknown / MVP 비필수 | MVP 필수 아님은 영구적 부재나 채택 선언이 아님. [L117](E:/AgentFit/Docs/project-proposal.md:117) |
| X01 | React | out_of_scope / 해당 출력 필드의 범위 밖 | 가상 운동 기록 서비스의 기술. [L80](E:/AgentFit/Docs/project-proposal.md:80) · [L89](E:/AgentFit/Docs/project-proposal.md:89) |
| X02 | Node.js | out_of_scope / 해당 출력 필드의 범위 밖 | 가상 운동 기록 서비스의 기술. [L80](E:/AgentFit/Docs/project-proposal.md:80) · [L89](E:/AgentFit/Docs/project-proposal.md:89) |
| X03 | 운동 기록 | out_of_scope / 해당 출력 필드의 범위 밖 | 가상 서비스 기능을 AgentFit 기능으로 넣지 않음. [L80](E:/AgentFit/Docs/project-proposal.md:80) · [L89](E:/AgentFit/Docs/project-proposal.md:89) |
| X04 | Codex | out_of_scope / 해당 출력 필드의 범위 밖 | 지원 Client 역할을 제품의 운영 AI 모델 역할로 바꾸지 않음. Client 역할 자체는 문서에 명시됨. [L115](E:/AgentFit/Docs/project-proposal.md:115) |
| X05 | MCP·Skill·Hook·Plugin·Project Rules | out_of_scope / 해당 출력 필드의 범위 밖 | 검토할 구성 종류이며 실제 외부 서비스 제공자 목록이 아님. [L103](E:/AgentFit/Docs/project-proposal.md:103) |
| U06 | Solar Pro 4 | unknown / 운영 Provider 미정 | 평가 후보의 존재는 보존하되 운영 채택으로 확정하지 않음. [L115](E:/AgentFit/Docs/project-proposal.md:115) |

> 브라우저에서 사용자가 고른 폴더에 적용하는 기능은 선택 확장이다. Local CLI, 모든 AI Client 지원, Shell 자동 실행과 인터넷 전체 도구의 실시간 자동 설치는 MVP 필수로 두지 않는다. OCR·이미지/표의 시각적 의미 해석·여러 문서 병합·팀 공유는 첫 기능에서 제외한다.

- `explicit_none`은 해당 기능·권한과 범위를 갖는 명시적 부정이다. `features=[]` 또는 GitHub 연동 없음으로 확대하지 않는다.
- 선택 확장·MVP 비필수 항목은 채택도 영구적 부재도 확정하지 않는다. 추출됐다면 문맥과 함께 보류/범위 설명에 남아야 한다.
- Codex를 지원 Client로 인식하는 것은 맞지만 운영 AI 모델에 넣는 것은 틀리다. GitHub 로그인은 실제 연동이며 같은 단어가 등장하는 위치만으로 인정하지 않는다.
- `F03`의 근거 제공, `F13`의 재승인 등 세부 의미와 domain의 요약 범위는 이 초안에서 검토 후 고정한다. 평가 결과를 본 뒤 기준을 바꾸지 않는다.

## 4. 파일과 검증 범위

- [gold-draft.json](gold-draft.json): 각 항목의 정확한 인용, 줄, Unicode 시작·끝 위치(끝 제외). 평가자만 사용.
- [expected-profile-draft.json](expected-profile-draft.json): 기존 Profile의 직렬화 형식을 확인하는 **기대값 표현 예시**. 입력 후보나 실제 AI 산출물이 아니며, 형식 검증만으로 세부 의미 36개가 모두 충족됐다고 판정하지 않음.
- [preparation-validation.json](preparation-validation.json): 원문 해시·인용 위치·필드 형식의 로컬 무결성 확인만 기록.
- [plan.md](plan.md): 문서 입력부터 최종 응답까지 단계별 평가 설계. 모델 호출·서비스 변경은 이번에 실행하지 않는다.
