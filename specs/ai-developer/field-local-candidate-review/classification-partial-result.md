# 분류 비교 부분 결과

> 이후 GLM 제공자 실패로 실행이 종료됐다. 전체 중단 결과는 [classification-result.md](classification-result.md)에 보존했다. 아래는 첫 완료 행의 관측 기록이다.

2026-10-01 실제 session38073이 진행 중이다. 원문·후보·모델 설정·실행기·계획·freeze는 변경하지 않는다. 현재 완료된 행은 PUBLIC-01/DeepSeek 한 건이며, 전체 비교 결론은 아직 내리지 않는다.

## 첫 DeepSeek 재현

- 응답 계약 유효,6호출/125.597819초.
- 이전 분류에서 누락된 C059/C061의 features/confirmed 복구:0/2.
- 이전에 features/confirmed였던 C066/C069/C071/C073 보존:0/4.
- 비기능 안내 C019/C026은 여전히 features/confirmed:비기능 제외0/2.
- Docker C113/C115의 deployment/confirmed 보존:2/2.
- 이전 저장된 분류 라벨과 달라진 후보:27개. 이 변화 개수를 정답·오답 수로 간주하지 않는다.

실제 라벨을 대조한 결과 C059/C061/C066/C069/C071/C073은 모두 other/irrelevant이고, C019/C026은 features/confirmed였다. 기술 목록의 제품 동작과 자체 호스팅·가입 안내 사이의 의미 구분에 실패한 관측이며, JSON 응답 형식 실패가 아니다.

## 과거 입력·코드 대조

API0으로 과거 freeze가 원래 실험 manifest의 hash와 일치하는지 확인했다. 원문 PUBLIC-01/07, 분류 모델명, 분류·필드 의미·모델 adapter·응답 처리·전송 모듈5개의 hash가 현재와 같았다([classification-input-history-audit.json](classification-input-history-audit.json)). 과거 전송 payload 원본은 보관하지 않았으므로 모든 전송 바이트가 같았다고 주장하지 않는다. 이번 결과 차이를 특정 코드 변경이나 원격 모델의 비결정성으로 단정할 근거도 아직 부족하다.

현재 첫 행은 검토 이전 분류에서도 기능 구분 문제가 남음을 보여준다. 이전 검토 비교는 기존 저장 라벨을 입력으로 사용했으므로, 그때의 GLM 검토 통과를 새 분석 전체에 그대로 적용할 수 없다. 이 관측만으로 모델 변경의 인과 효과·반복 안정성·전체 정확도를 확정하지 않는다. 이어지는 GLM 분류와 공개07·합성 비교는 사전등록된 조건 그대로 완료한다.
