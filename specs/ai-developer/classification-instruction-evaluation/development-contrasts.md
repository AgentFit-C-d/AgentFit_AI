# 이름·표현 의존성 점검용 합성 대조 초안

아래는 새 공개 문서와 별도인 **직접 작성한 개발 자료**다. 모델 입력용 일반 지침에는
이름·문장·정답을 넣지 않는다. 이번에 모델에 보내거나 자동 검증기로 구현하지 않는다.
향후 사용할 때도 두 arm의 원문·후보·정답을 동일하게 고정한다.

## 이름과 문장 순서 대조

가상 제품 `Teren`의 현재 요구사항 문서 두 변형을 만든다.

| 변형 | 지원 플랫폼 문장 | 실제 외부 연동 문장 | 순서 |
| --- | --- | --- | --- |
| D1 | Teren is accessible through the Aven browser. | Teren sends invoices to the Belis billing service through its API. | 플랫폼→연동 |
| D2 | The Belis browser can be used to access Teren. | Invoice delivery in Teren uses the API of the Aven billing service. | 연동→플랫폼 |

같은 이름이 다른 변형에서 반대 역할을 갖는다. 브라우저명 후보는 `other/irrelevant`,
실제 청구 서비스명 후보는 `external_integrations/confirmed`, 청구서 전송 동작 후보는
`features/confirmed`다. 이름별 고정 필드를 학습하는 예외를 두지 않는다.

## 외관과 실제 기능 대조

| 원문 초안 | 정확한 후보 | 정답 초안 |
| --- | --- | --- |
| Teren has a polished, readable interface. | polished, readable interface | other/irrelevant |
| Readers can switch Teren's interface to a high-contrast mode. | switch Teren's interface to a high-contrast mode | features/confirmed |
| Teren automatically groups incoming records by the user's saved rules. | automatically groups incoming records by the user's saved rules | features/confirmed |
| Records can be exported as a file; the interface looks elegant. | Records can be exported as a file | features/confirmed |
| 같은 문장 | the interface looks elegant | other/irrelevant |

마지막 혼합 문장은 절의 앞뒤 순서를 바꿔도 같은 정답을 요구한다.
UI 전체 제외, 명사구 기능 제외, 자동 처리 제외와 같은 과도한 누락을 잡기 위한 대조다.

## 확정·미정 대조

| 현재 대상 제품에 대한 문맥 | 서비스명 후보의 정답 초안 |
| --- | --- |
| Teren already supports account sync with the Merin service. Users may enable it. | external_integrations/confirmed: 이미 제공하는 선택 기능 |
| The team is considering whether Teren should integrate with Merin; no decision has been made. | external_integrations/tentative: 검토 중 |
| Teren does not integrate with Merin. | external_integrations/negated: 명시적 부정 |
| Merin is mentioned as a possible partner; its role in Teren is unspecified. | other/tentative: 근거를 보존하고 확인 필요 |

고정 응답 로컬 테스트는 이 정답으로 데이터 보존/집계가 되는지만 검증한다.
모델이 변형 문장에서 같은 의미를 판단하는지는 별도 실제 호출 없이는 검증되지 않는다.
