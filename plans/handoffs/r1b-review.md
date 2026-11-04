# 1주차 R1-B 지휘 검수

기준일: 2026-11-05 · 작업 시작 11/4
상태: 지휘 1차 검수·수정·재검수 통과, 사용자 2차 확인 대기
기준: [연결 규격](../r1b-contract.md) · [주차별 기록](../weekly-development-log.md)

## 배정과 중간 커밋

- 사용자 `그러면 계속 개발 진행해보자` 요청으로 R1-B 착수 허용
- 실제 물리 키보드를 검수했다는 별도 답변은 받지 않음
- 로직: 순수 4방향 선택·실제 거리 기반 보행 위상
- UI·에셋: 4방향×idle/walk1/walk2, 실제 변위 연결·렌더·입력 회귀
- 지휘: 연결 규격·독립 검수·수정 요청·Git, 다음 R2 착수 금지
- `176fa2c`: 방향·보행 연결 규격
- `5e4ee7e`: 15개 자동 검사·독립 검토를 통과한 방향/보행 로직
- `ec394ae`: 전체 atlas 교정 실패 후 문제 자세 2개를 별도 소스로 연결하는 예외
- `e27a5b0`: 4방향·짧은 보행 연결과 발 교대·공통 접지 root 수정본

## 실제 확인과 수정 요청

| 항목 | 관찰 결과 | 처리 |
| --- | --- | --- |
| 순수 로직 | 지휘 실행 15/15 통과, 독립 검토에서 실제 오류 미발견 | 로직 중간 커밋 |
| 실제 변위 연결 | move_player 전후 변위·aim 뒤 update·smoke 강제 배치 제외 확인 | 최종 통합 회귀 예정 |
| 12셀 원본 | 뒤쪽 두 방향의 발 교대 확인, 앞쪽 두 방향 walk2는 같은 발 전진 | UI에 교정 요청 |
| 전체 atlas 표적 편집 | 앞 보행의 반대 발 전진이 여전히 불명확 | 수정 시도 미채택, 문제 두 자세만 별도 제작 |
| 앞 보행 2자세 별도 제작 | 원본에서 FR은 왼쪽, FL은 오른쪽 화면 다리가 기존 walk1과 반대로 전진함을 지휘 확인 | 추가 생성 없이 채택, 크기·접지 연결 후 재검수 |
| 숨김 Windows SDL | 실제 렌더러로 12자세·벽 앞뒤 3장 캡처, 완전 종료 | 수정 전 시각 검수 증거로만 사용 |
| 머리·상체 흔들림 | 프레임별 sole 중점 pivot으로 같은 방향에서 최대 약 8px 차이 | 몸 기준 공통 발 root로 정렬 요청 |

검수 출력은 Git에서 제외되는 `output/review/R1-B/`에 저장
`native_review.py`는 실제 Windows SDL 창을 숨김으로 생성하고 PlayerVisual.update/draw·main.capture를 사용
창 표시·사용자 OS 입력·물리 키보드·실제 조작감 검수와 구분함

## 최종 재검수

앞 보행 교정 소스·공통 몸 기준 발 root·메타·소스 선택 연결을 수신해 아래 재검수 수행

```powershell
.\.venv\Scripts\python.exe -m compileall -q game
.\.venv\Scripts\python.exe -B -m unittest discover -s game/tests -v
.\.venv\Scripts\python.exe -B output/review/R1-B/native_review.py
```

- compileall 종료 코드 0, 전체 자동 **66/66 통과**
- 실제 main.run의 SDL dummy 사건 재생: 키 유지/해제·포커스·벽 앞 idle·마우스 방향·후진/옆걸음·smoke 강제 배치 제외 확인
- 두 실제 텍스처의 canvas/nearest, 중복 close·두 번째 소스 크기 실패 시 선행 소스 정리 검사 통과
- 독립 검토: 실제 두 PNG SHA256·상대 경로·캔버스·12프레임 clip/발 root/배율 정합, 추가 blocker 없음
- 숨김 **Windows SDL**에서 실제 PlayerVisual.update/draw와 main.Renderer로 12자세 contact sheet·벽 앞·벽 뒤 **3장** 생성, 지휘 직접 이미지 검토
- 앞 보행 교대·4방향 앞/등·택배/방망이 손·몸 크기·발 기준선·벽 앞뒤 가림 확인
- 머리 높이 차이: front_right **0.539px**, back_right **0px**, back_left **0px**, front_left **0.527px**
- `renderer.close()` 정상, `SDL_WasInit(0)==0`, 검수 동안 모든 PNG·메타 SHA256 보존

최종 증거: output/review/R1-B/native-contact-sheet.png, native-wall-front.png, native-wall-behind.png, native-review.json
검수용 fixture의 거리 입력은 물리 키보드나 실제 플레이 검증이 아님

## 한계

- 초판 4방향·각 idle+보행 2자세이며 정밀한 다방향 애니메이션 완성본이 아님
- 생성 PNG의 희미한 알파 가장자리·프레임별 세부 그림 차이는 남음. 정확한 64px 원본 격자를 주장하지 않음
- 실제 키보드·OS 창 전환 조작·시간에 따른 보행 체감은 사용자 2차 확인 필요
- 검수 후 창 종료, 전투·좀비·손전등·배달·R2와 푸시 미착수

## 사용자 2차 확인

지휘 검수본을 프로젝트 루트에서 실행

```powershell
.\.venv\Scripts\python.exe game/main.py
```

1. 마우스로 사방을 조준할 때 몸 방향·택배/방망이 손 확인
2. WASD 걷기·후진·옆걸음의 발 교대와 상체 크기 확인
3. 벽에 막혔을 때 보행 정지, 키 해제·다른 창 전환 뒤 입력 잔류 확인
4. 벽 앞뒤 가림과 발 접지 확인

사용자 2차 확인·다음 진행 요청 전 R2 전투를 배정하지 않음
