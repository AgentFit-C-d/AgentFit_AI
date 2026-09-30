# runtime-purpose-v1 결과: 채택 보류

session20703 exit0,6요청22호출/재시도0/실패0, 이전115JSON hash불변. 외부0 adapter 검증3건 통과. 최종 감사는 audit.json이다.

- PUBLIC-01 두 번 모두 기존에 잘못 제외된 제품 용도4개를 유지했다. 비기능 안내2개는 계속 제외했다.
- PUBLIC-07 명시적 기능14개를 두 번 모두 유지했다. 겹치는 긴/짧은 인용은 별도 중복 문제다.
- 합성 기대12건은 baseline과 purpose 각각12/12였다. 이 합성 사례만으로 일반화나 실제 정확도를 주장하지 않는다.
- **회귀 발견:** PUBLIC-01의 유효한 Docker 배포 근거 C113/C115 등도 두 번 모두 not_product_fact로 제외됐다. 기능에 대한 배포 안내 제외 규칙이 deployment 필드에도 적용된 것으로 의심된다. TypeScript/Tailwind 배지 근거의 제외도 한 실행에서 변했다.
- **누락 검토도 영향:** 합성 문서에는 제품명이 있지만 후보에는 없다. baseline은 project_name 누락을 표시했으나 v1은 missingFields=[]였다. 기능 판정만으로 개선을 선언할 수 없는 추가 회귀다.

따라서 v1은 제품 기본 적용하지 않는다. 다음 한 변수 수정은 규칙을 features 필드에만 한정하고 다른 필드는 본래 정의로 판단하라는 명시적 범위다. 기존 결과는 보존하고, 배포·frontend·backend·database 양성 항목을 함께 넣은 합성 자료로 필드 간 영향을 검증한다. 임시 gold/과거 점수는 변경하지 않는다.
