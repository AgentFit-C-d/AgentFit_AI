# 진행 상태

- branch: feature/semantic-role-service-path; base: 5de4020.
- 큰 goal paused, 이번 서비스 연결·문서 검증만 수행 후 종료.
- 기존 미커밋/중단 문서·실험 결과 보존. API키·원문 민감정보 출력 금지.
- 확인: integrated-nvidia worker가 semantic_assessment를 전달하지 않아 False로 일반 분류 사용. default는 Solar; deploy manifest/실제 원격설정 아직 확인 안 됨.
- 계획: 서비스 NVIDIA 경계에 True 연결, 공개 v2 그대로. 로컬 실제 SDK/HTTP/worker 고정 응답부터 검증. 신규 공개 문서 정답은 실험 전 고정.
- 호출 상한: 무료 DeepSeek/GLM만, 4문서 요청/256모델 호출/전체2시간, 요청1800초·64호출, 재시도0. 오류 시 전체중단, 유료/Luna 없음.
- 다음: 환경/신규 문서 조사, RED/GREEN, 문서 end-to-end 비교. 사용자 요청이 승인한 연결 범위에 한정.

## 현재 증거

- 작업 셸 모드/토큰/API키 없음; E:/AgentFit/.env는 키만 있고 모드/토큰 없음; 자동로딩없음. 조회 당시 로컬Python프로세스 없음. 실제 원격배포 manifest/commit/env 미제공.
- 기본체크아웃 E:/AgentFit은 별개 feature/semantic-review-model-routing(5e6910f), 다른 사용자 변경 다수. 수정하지 않음. 이번 코드가 자동 배포·기본체크아웃에 반영됐다고 주장하지 않음.
- worker integrated-nvidia options에 semantic_assessment=True 연결. 기존 v2 구조 재사용. 기본Solar/혼합은그대로.
- RED6사례: metadata없음/역할오분류. GREEN6사례: 실제SDK/child/TCP/HTTP 정상정보11/11 유지.
- 고정HTTP비교 6문서18후보: 오확정제안6→0, 정상누락0→0, 확인질문11→12, 보류후보0→7, 필드미정유실1→0. 전후실행결과보존.
- unit 1,279 실행 / 7 skip, contract 47 pass, core 8 pass. 낡은 runtime fixture 수정 후 전체 runtime 36 pass (142.123초, runtime2.log).
- 호출수변화: 의미분류8후보단위로10후보 fixture는5→6호출. 후보가8이하인문서fixture는5그대로. 프로덕션호출상한64그대로.
- 신규linkding README pinned27b7303, 기존기록검색0건. Documenso원본과함께선택. gold 사전동결(명시정상9+19), 모호/미포함출력은사람검토.
- live session84423: 4요청 예산 평가 진행 중. freeze.json이 분석 모듈 128개×전후 및 평가 코드/문서/정답 해시를 고정한다. 실행 중 해당 파일 수정 금지.
- linkding 전후 완료: 오제안 1→2, 정상 누락 1→5 (19개 기준), 질문 객체 10→11, 처리 564.850→1,284.480초, 호출 10→14. **실제 품질 악화.** Documenso 전후 평가 진행 중.
- 전후 grounded 동일 68개, 변경 후 최종 기록 68/68 보존. supported 16 / 보류 17 / 제외 35. 보류 17개 전부 질문 연결, 필드 미정 13개는 질문 1개에 묶임. 소실과 정상 Profile 제안 누락은 구분.
- 새 오류의 최초 단계는 의미 분류: Firefox/Chrome을 외부 서비스로, 프로젝트명을 기능으로, Django를 외부 서비스로 분류. 서버가 모순을 보류하면서 정상 제안도 감소. 운영 채택 권고 불가, 결과를 숨기거나 기준/코드를 실험 중 수정하지 않음.
- 최초 오류: Clean UI 설명을 최초 분류에서 features/confirmed로 설정, 검토에서 유지. 확장 기능은 grounded 단계에 없음. 원시 추출 기록 부재로 추출 누락과 근거 거절을 구분할 수 없음.
- 독립 reviewer semantic_role_service_review 완료: Critical/Important 없음. 부분 gold/별칭 채점 제한을 보고서에 명시. 실제 모델 정확도는 당시 결과 없어 판단 보류.
- 코드 commit 4b54f60 원격 feature/semantic-role-service-path에 push 완료. CI run 36829122975 네 job 모두 success. 고정 파일 262개 해시 재확인: 변경 0개.
- 남은 작업: 실제 결과와 후보 보존 대조, 결과 보고서 확정, 문서 commit/push, CI 확인 후 종료. 기존 큰 goal 자동 재개 금지.
