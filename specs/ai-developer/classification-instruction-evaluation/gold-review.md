# 별도 문서 평가 사례와 정답 초안

**아직 사용자 정답 승인을 받지 않은 초안이다. 모델 실행 결과는 없다.**
명확 초안30개(정상16 / 필드 밖13 / 명시적 부정1)와 사람 검토2개를 분리한다.
전체32개 후보는 두 arm에서 모두 보존한다. 정확한 코드포인트 위치·단위 ID는 gold-draft.json에 있다.
원문은 각 라이선스와 함께 변경 없이 보존했다. 아래 판정 이유는 평가 정답이며 모델 입력에 넣지 않는다.

## 검토 원칙

- 지원 OS와 단순 외관·품질 설명은 현재 Profile 필드 밖이다. 사실 자체가 거짓이라는 뜻은 아니다.
- 실제 연동, 화면 모드, 검색·정리·자동 처리·CLI 동작은 명시된 기능으로 보존한다.
- 명확한 필드 밖 표현은 other/irrelevant, 명시적 부정은 해당 필드/negated, 모호함은 tentative로 보존한다.
- 모든 정답은 문서의 정확한 선택 범위와 전체 문맥 기준이다. 이름만 보고 판단하지 않는다.

## FR — yang991178/fluent-reader

[고정 공식 문서](https://github.com/yang991178/fluent-reader/blob/58139987094f05a6f5a662070606d17635ff188e/README.md) · commit 58139987094f05a6f5a662070606d17635ff188e

| 사례 | 원문 후보(줄) | 기대 field / status → gate | 이유 |
| --- | --- | --- | --- |
| FR01 (C001) | Windows 10 ([L15](https://github.com/yang991178/fluent-reader/blob/58139987094f05a6f5a662070606d17635ff188e/README.md#L15)) | other / irrelevant → excluded | 설치 가능한 클라이언트 OS. 제품의 외부 서비스나 구현 기술을 뜻하지 않는다. |
| FR02 (C002) | Linux ([L19](https://github.com/yang991178/fluent-reader/blob/58139987094f05a6f5a662070606d17635ff188e/README.md#L19)) | other / irrelevant → excluded | 사용자 실행 OS. 지원 플랫폼을 배포 선택으로 바꾸지 않는다. |
| FR03 (C003) | A modern UI inspired by Fluent Design System ([L31](https://github.com/yang991178/fluent-reader/blob/58139987094f05a6f5a662070606d17635ff188e/README.md#L31)) | other / irrelevant → excluded | 선택 범위는 외관·디자인 설명이며 뒤의 다크 모드 기능을 포함하지 않는다. |
| FR04 (C004) | full dark mode support ([L31](https://github.com/yang991178/fluent-reader/blob/58139987094f05a6f5a662070606d17635ff188e/README.md#L31)) | features / confirmed → supported | 단순 미관 평가와 달리 구체적으로 제공되는 화면 모드. 같은 문장의 정상 기능 대조군. |
| FR05 (C006) | Inoreader ([L33](https://github.com/yang991178/fluent-reader/blob/58139987094f05a6f5a662070606d17635ff188e/README.md#L33)) | external_integrations / confirmed → supported | 대상 리더가 실제 동기화를 지원하는 명명된 외부 서비스. |
| FR06 (C007) | Feedbin ([L33](https://github.com/yang991178/fluent-reader/blob/58139987094f05a6f5a662070606d17635ff188e/README.md#L33)) | external_integrations / confirmed → supported | 이미 제공되는 선택형 서비스 연동. 모든 이용자의 필수 설정일 필요는 없다. |
| FR07 (C005) | Google Reader API ([L32](https://github.com/yang991178/fluent-reader/blob/58139987094f05a6f5a662070606d17635ff188e/README.md#L32)) | other / irrelevant → excluded | 여기서는 호환 API 규약이다. 특정 원격 서비스 제공자 이용을 뜻하지 않는다. |
| FR08 (C008) | Importing or exporting OPML files ([L34](https://github.com/yang991178/fluent-reader/blob/58139987094f05a6f5a662070606d17635ff188e/README.md#L34)) | features / confirmed → supported | 문서에 명시된 파일 가져오기·내보내기 동작. 형식명과 전체 동작을 구별한다. |
| FR09 (C009) | Search for articles with regular expressions or filter by read status ([L36](https://github.com/yang991178/fluent-reader/blob/58139987094f05a6f5a662070606d17635ff188e/README.md#L36)) | features / confirmed → supported | 검색·필터링이라는 사용자 동작이 구체적으로 명시됐다. |
| FR10 (C010) | Organize your subscriptions with folder-like groupings ([L37](https://github.com/yang991178/fluent-reader/blob/58139987094f05a6f5a662070606d17635ff188e/README.md#L37)) | features / confirmed → supported | 폴더 형태의 구독 정리 기능. linkding의 태그 정리와 별도 표현인 정상 대조군. |
| FR11 (C011) | Hide, mark as read, or star articles automatically as they arrive with regular expression rules ([L39](https://github.com/yang991178/fluent-reader/blob/58139987094f05a6f5a662070606d17635ff188e/README.md#L39)) | features / confirmed → supported | 규칙에 따른 자동 상태 변경. 사용자 클릭이 없어도 제품 기능이다. |
| FR12 (C012) | Fetch articles in the background and send push notifications ([L40](https://github.com/yang991178/fluent-reader/blob/58139987094f05a6f5a662070606d17635ff188e/README.md#L40)) | features / confirmed → supported | 백그라운드 수집·알림 동작. 원문에 없는 알림 제공자 이름은 추론하지 않는다. |
| FR13 (C014) | Paypal ([L53](https://github.com/yang991178/fluent-reader/blob/58139987094f05a6f5a662070606d17635ff188e/README.md#L53)) | other / irrelevant → excluded | 개발 후원을 위한 기부 링크이며 대상 제품의 런타임 결제 연동이 아니다. |
| FR14 (C015) | React ([L76](https://github.com/yang991178/fluent-reader/blob/58139987094f05a6f5a662070606d17635ff188e/README.md#L76)) | frontend / confirmed → supported | Developed with 문맥의 채택된 UI 구현 프레임워크. |
| FR15 (C000) | desktop RSS reader ([L5](https://github.com/yang991178/fluent-reader/blob/58139987094f05a6f5a662070606d17635ff188e/README.md#L5)) | project_type / confirmed → supported | 현재 대상 제품의 명시적인 데스크톱 제공 형태. 인접한 modern 수식어 때문에 누락하면 안 된다. |
| FR16 (C013) **사람 검토 필요** | Support for other RSS services ([L42](https://github.com/yang991178/fluent-reader/blob/58139987094f05a6f5a662070606d17635ff188e/README.md#L42)) | 필드 사람 검토 / tentative → needs_confirmation | 모금 중인 추가 지원이다. 구체적인 서비스가 없어서 features로 보존할지 other로 둘지는 사람 검토 필요. confirmed는 허용하지 않는 초안. |

## LS — localsend/localsend

[고정 공식 문서](https://github.com/localsend/localsend/blob/c5bbe3630bb50e0de8253502b41523c4a58825bb/README.md) · commit c5bbe3630bb50e0de8253502b41523c4a58825bb

| 사례 | 원문 후보(줄) | 기대 field / status → gate | 이유 |
| --- | --- | --- | --- |
| LS01 (C007) | Android ([L104](https://github.com/localsend/localsend/blob/c5bbe3630bb50e0de8253502b41523c4a58825bb/README.md#L104)) | other / irrelevant → excluded | Compatibility 표의 현재 지원 OS. 같은 행의 과거 버전 지원 사실과도 구별한다. |
| LS02 (C008) | Windows ([L107](https://github.com/localsend/localsend/blob/c5bbe3630bb50e0de8253502b41523c4a58825bb/README.md#L107)) | other / irrelevant → excluded | 호환 플랫폼의 현재 행 이름. 외부 서비스·배포 환경으로 확정하지 않는다. |
| LS03 (C004) | fast and reliable ([L46](https://github.com/localsend/localsend/blob/c5bbe3630bb50e0de8253502b41523c4a58825bb/README.md#L46)) | other / irrelevant → excluded | 선택 범위는 속도·신뢰성 수식어만이다. 동작을 명시한 별도 후보와 구별한다. |
| LS04 (C001) | securely share files and messages with nearby devices over your local network without needing an internet connection ([L23](https://github.com/localsend/localsend/blob/c5bbe3630bb50e0de8253502b41523c4a58825bb/README.md#L23)) | features / confirmed → supported | 보안 수식어가 있어도 파일·메시지 공유 동작은 명확하다. 인터넷 서비스 연동을 새로 만들지 않는다. |
| LS05 (C002) | REST API ([L46](https://github.com/localsend/localsend/blob/c5bbe3630bb50e0de8253502b41523c4a58825bb/README.md#L46)) | other / irrelevant → excluded | 장치 간 통신 방식. 구체적인 외부 제공자가 아니다. |
| LS06 (C003) | HTTPS ([L46](https://github.com/localsend/localsend/blob/c5bbe3630bb50e0de8253502b41523c4a58825bb/README.md#L46)) | other / irrelevant → excluded | 선택 범위는 통신 프로토콜명 자체다. 서비스나 백엔드 프레임워크로 올리지 않는다. |
| LS07 (C005) | auto-update ([L64](https://github.com/localsend/localsend/blob/c5bbe3630bb50e0de8253502b41523c4a58825bb/README.md#L64)) | features / negated → excluded | 앱이 자동 업데이트를 제공하지 않는다고 명시한다. 다른 제품 문서의 업데이트를 옮겨오면 안 된다. |
| LS08 (C009) | The app will use this file to store settings instead of the default location ([L130](https://github.com/localsend/localsend/blob/c5bbe3630bb50e0de8253502b41523c4a58825bb/README.md#L130)) | features / confirmed → supported | Portable Mode의 이미 제공되는 설정 저장 동작. will이 있어도 미정 계획으로 간주하지 않는다. |
| LS09 (C010) | start the app hidden (only in tray) ([L136](https://github.com/localsend/localsend/blob/c5bbe3630bb50e0de8253502b41523c4a58825bb/README.md#L136)) | features / confirmed → supported | 현재 제공되는 트레이 시작 모드. v1.14 이전 설정 설명과 현재 플래그를 구별한다. |
| LS10 (C015) | Weblate ([L202](https://github.com/localsend/localsend/blob/c5bbe3630bb50e0de8253502b41523c4a58825bb/README.md#L202)) | other / irrelevant → excluded | 기여자의 번역 관리 도구이며 사용자 파일 공유 기능이 이용하는 외부 연동이 아니다. |
| LS11 (C006) | Play Store ([L68](https://github.com/localsend/localsend/blob/c5bbe3630bb50e0de8253502b41523c4a58825bb/README.md#L68)) | other / irrelevant → excluded | Download 표의 배포처. 제품 런타임에서 그 서비스에 데이터를 보내는 근거가 아니다. |
| LS12 (C014) | To select the destination without an interactive device list, pass its exact alias ⏎ or IP address ([L181](https://github.com/localsend/localsend/blob/c5bbe3630bb50e0de8253502b41523c4a58825bb/README.md#L181)) | features / confirmed → supported | 같은 README가 설명하는 공식 CLI의 수신자 지정 동작. GUI 버튼이 없어도 기능이다. |
| LS13 (C013) | Flutter ([L154](https://github.com/localsend/localsend/blob/c5bbe3630bb50e0de8253502b41523c4a58825bb/README.md#L154)) | frontend / confirmed → supported | 앱 빌드·실행 명령과 요구 버전으로 채택을 확인하는 UI 프레임워크. 설치라는 동작 자체를 기능으로 만들지는 않는다. |
| LS14 (C012) | maximum security ([L142](https://github.com/localsend/localsend/blob/c5bbe3630bb50e0de8253502b41523c4a58825bb/README.md#L142)) | other / irrelevant → excluded | 주변의 암호화 구현과 구별되는 품질 평가 표현 자체다. |
| LS15 (C011) **사람 검토 필요** | All data is sent securely over HTTPS ([L142](https://github.com/localsend/localsend/blob/c5bbe3630bb50e0de8253502b41523c4a58825bb/README.md#L142)) | features / tentative → needs_confirmation | 전체 데이터 암호화라는 절대 표현과 230행의 양쪽 장치 암호화 해제 안내가 공존한다. 기본 모드·옵션 관계인지 상충인지 사람 검토 필요. 주 정확도 점수 제외. |
| LS16 (C000) | LocalSend ([L23](https://github.com/localsend/localsend/blob/c5bbe3630bb50e0de8253502b41523c4a58825bb/README.md#L23)) | project_name / confirmed → supported | 설명 본문이 명명하는 현재 대상 제품. 제목-only 근거 제약과 무관한 정상 이름 대조군. |

## 사람 검토가 필요한 두 항목

- FR16: 모금 중인 추가 RSS 지원을 features/tentative로 남길지 other/tentative로 남길지 확인이 필요하다. 구체적인 서비스명이 없어 외부 제공자를 만들지 않는다.
- LS15: 142행의 전체 데이터 암호화와 230행의 암호화 해제 안내가 기본 모드·선택 옵션 관계인지, 현재 문서의 모순인지 검토가 필요하다. 초안은 features/tentative다.
- 두 항목의 raw confirmed/supported 및 근거 선택은 결과 표에 그대로 공개한다. 주 정확도 점수 제외를 성공 처리로 해석하지 않는다.

## 비교 전 점검할 판단

- FR03 외관 설명과 FR04 다크 모드는 같은 문장의 서로 다른 후보다. UI를 일괄 제외하지 않는다.
- FR05/FR06은 이미 제공되는 선택형 연동이다. 검토 중인 계획으로 보류해서는 안 된다.
- LS08의 will은 현재 Portable Mode 동작 설명이다. 미래형 표현만으로 미정으로 바꾸지 않는다.
- LS12는 문서가 설명하는 공식 CLI 동작까지 대상 범위에 포함한 초안이다.
- LS03은 fast and reliable 수식어만 선택했다. 인접한 통신 기능 문장 전체를 품질 설명으로 지우는 사례가 아니다.
- 새 두 문서에 대한 기존 U와 U+C 성능은 모두 미측정이다. 이 표는 측정 결과가 아닌 정답 검토 자료다.
