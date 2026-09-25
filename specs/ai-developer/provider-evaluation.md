# AI Provider 1차 평가: Solar Pro 4

## 결정과 상태

- 2026-09-25 사용자 결정: AgentFit이 설정을 추천·생성할 초기 Client는 Codex다. Claude Code는 초기 지원 대상이 아니다.
- 문서 분석의 1차 평가 모델은 Upstage Solar Pro 4(`solar-pro4`)다. **최종 운영 Provider 선정이나 실제 품질 통과를 뜻하지 않는다.**
- 2026-09-25 사용자 결정: 실험은 로컬에서 먼저 수행한다. 배포 단계에서 서버 `.env`에 키를 설정한다. 평가 호출 예산의 별도 상한은 두지 않지만 표본·호출 횟수·실제 비용은 기록한다.
- 2026-09-25 사용자 확인: Upstage API 키를 로컬 `.env`에 설정했다. 키 값은 읽어 출력하거나 문서에 기록하지 않았다.
- 기존 첫 Feature Plan의 OpenAI Responses 설계는 이전 기준안이다. Provider별 구현 파일·SDK·키 이름·보관 고지는 평가 결과를 반영해 구현 전에 재정리한다. 공통 Project Profile과 사용자 검토 계약은 유지한다.
- 합성 텍스트 1건의 로컬 API smoke test는 아래와 같이 수행했다. 전체 품질 평가·FastAPI 구현·Spring Boot 연동은 아직 수행하지 않았다. 외부 패키지는 설치하지 않았다.

## 2026-09-25 로컬 smoke test

- 실행: `node scripts/solar-smoke.mjs` (Node.js 22.16.0의 내장 `fetch` 사용, 추가 패키지 없음).
- 공식 Chat Completions API에 `solar-pro4`와 strict `json_schema`로 합성 텍스트 1건을 1회 요청했다. 문서에는 확정된 프로젝트명과 미정 DB가 있다.
- 결과: HTTP 성공, 응답 모델 `solar-pro4-260806`, 구조·프로젝트명·DB `null` 검사 모두 통과. 입력 114 tokens, 출력 18 tokens.
- 실제 응답 원문과 키는 파일·로그에 저장하지 않았다. 이 한 건은 PDF 추출, 10개 Profile 필드, 근거 위치, 의미 반례, 오류 처리, 지연 목표 또는 최종 Provider 채택을 입증하지 않는다.

## 평가 순서

1. **계약 확인:** Upstage 공식 Chat API에서 모델 ID, `json_schema` 구조화 출력, 거절·불완전 응답·시간 초과, 요청·응답 형식, 인증·보관 조건을 확인한다. OpenAI Responses와 같은 API라고 가정하지 않는다.
2. **사전 정답 고정:** 합성 FACT 9개(입력 유형별 3개), SEM 12개(부정·후보/확정·현재/미래·다른 대상·상충·문맥 제한 각 2개), NORMAL 30개(입력 유형별 10개), ERROR 사례의 기대 필드·미정·근거를 모델 출력 전에 고정한다.
3. **로컬 제한 시험:** 승인된 합성 텍스트로 구조화 출력, 미정·근거·의미 반례, 안전한 실패를 먼저 확인한다. 모델명·설정·Prompt·호출 횟수·비용·성공/실패 지연을 기록한다. 이 결과는 전체 기능 완료 판정이 아니다.
4. **실제 흐름 평가:** Full Stack A의 저장·표시 연동 후 FACT 정확도 90% 이상, SEM 필수 대상 필드 모두 정답, NORMAL 첫 요청 성공 30개 중 최소 29개, 결과 또는 명시적 실패 안내 p95 60초 이내를 각각 판정한다. 재시도·오류·실패 표본을 성공으로 세지 않는다.
5. **선정:** 계약 적합성, 품질, 지연, 비용, 데이터 처리·보관 조건을 함께 기록하고 팀의 최종 Provider 결정을 Plan·Tasks·Quickstart·역할 문서에 반영한다. 미달 시 원인을 기록하고 비교 후보를 검토한다.

## 선행 준비와 협업 계약

- 실제 Solar 로컬 호출은 루트 `.env`의 `UPSTAGE_API_KEY`를 사용한다. 루트 `.gitignore`가 `.env`를 제외한다. 키 값은 채팅·문서·Fixture·로그에 남기지 않는다. 최종 앱 변수 계약은 Provider 선정 후 확정한다.
- 배포 시 서버 `.env`에 키를 설정하며, 로컬 키나 값을 저장소·배포 산출물로 복사하지 않는다. 배포 환경의 Secret 주입·보관 검증은 별도 단계다.
- Full Stack A와 분석 입력·출력·안전한 오류, Provider 시간 제한, 저장·상태 책임을 맞춘다. Frontend와 `null`·빈 배열·출처·근거 위치 표시를 맞춘다.
- Codex의 설정 형식·권한·지원 버전은 후속 Config Feature에서 공식 문서와 실제 조합으로 검증한다. 개발에 Codex를 사용한다는 사실만으로 사용자 환경의 적용·연결이 검증된 것은 아니다.

## 공식 자료

- [Upstage Solar Pro 4 소개](https://www.upstage.ai/blog/en/solar-pro-4)
- [Upstage Chat API](https://console.upstage.ai/api/chat)
- [OpenAI Docs: Skills](https://developers.openai.com/plugins/concepts/skills)
