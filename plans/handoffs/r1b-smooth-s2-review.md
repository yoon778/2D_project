# 1주차 R1-B-S2 지휘 검수

기준일: 2026-11-05 · baseline 358978f
상태: 세 방향 적용·방향별/통합 지휘 검수 통과, 1주차 실제 루프 검수 완료·사용자 2차 확인 대기
기준: [S2 계약](../r1b-smooth-s2-contract.md)

## 요청·배정·중간 기록

- 사용자가 나머지 세 방향의 8장 보행·두 채팅 지시·게임 적용·검수·중간 커밋 요청
- 세 방향을 S2 한 묶음으로 배정. back_right→back_left→front_left를 지휘 검수·수정·커밋 후 순차 진행
- S1 front_right 전체 프레임/소스·기존 모든 idle·PNG는 정확히 보존
- 로직 담당은 기존 N장 선택을 재사용하며 실제 네 방향 전환·후진/옆걸음·벽 정지/슬라이딩 검사 5개 추가
- 지휘 집중 검사 26/26·독립 검토 통과. 순수 로직 오류 없어 구현 변경 없음
- `2c23e08`: S2 계약 확정
- `f830404`: 네 방향 보행 전환·정지 집중 검사

## 방향별 검수

| 방향 | 제작·수정 | 지휘 검수 | 커밋 |
| --- | --- | --- | --- |
| back_right | 첫 그림의 같은 다리 반주기 반복을 표적 교정1회, 1/5·3/7 반전 확인 | 전체79개·숨김Windows4장/60프레임·8→1 경계 검토 통과, 머리proxy0.31194px·baseline/SHA 보존 | `9b6bb29` |
| back_left | 첫 그림의 1/5 반복·4/8 유사를 표적 교정1회, 1/5 반대 지지 확인 | 전체79개·숨김Windows4장/60프레임·8→1 경계 검토 통과, idle포함 머리proxy0.35120px·이전 방향 보존 | `2e44658` |
| front_left | 첫 생성1회, 1/5·3/7·4/8 반대 다리·상승 구분 확인, 추가 교정 없음 | 전체79개·숨김Windows4장/60프레임·8→1 경계 검토 통과, idle포함 머리proxy0.45795px·이전 방향 보존 | `4b4d657` |

표적 교정 뒤에도 비슷한 상승 실루엣 등 생성 그림의 한계는 별도로 기록함
단순 프레임 수·메타 수치 통과만으로 실제 자세 품질을 통과 처리하지 않음

## 검수 수단

검수 출력은 Git 제외 폴더 output/review/R1-B-S2/에 저장
baseline.json에 S1·idle·기존 소스/PNG를 기록하고 최종 파일과 독립 비교

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s game/tests -q
.\.venv\Scripts\python.exe -m compileall -q game
.\.venv\Scripts\python.exe -B output/review/R1-B-S2/native_review.py --direction back_right
```

각 방향의 숨김 Windows SDL 실제 렌더: idle+walk8 contact sheet, 다른 방향 샘플·벽 앞뒤, 조준 방향으로 이동한 2초/60프레임
실제 core 변위→aim→PlayerVisual.update/draw, 90px/s·32px 주기 유지
프레임 기대값·nearest/canvas·고정 배율/root·머리 상단 높이 차이3px 이내·SHA256 보존·SDL 완전 종료 확인
고정 순서/주기 경계 캡처의 시각 검토와 사용자 실제 키보드·연속 보행 체감은 구분
실제 main.run 입력 연결은 별도 SDL dummy 사건 회귀로 검사함

## S2 최종 통합 결과

- 전체79개·compileall 통과, 최종 네 방향 모두 idle1+walk8의36자세·6소스
- 최종 메타에서 네 방향 각4장/60프레임 Windows fixture 실행, 16장 시트/가림 캡처와240장 이동 프레임 생성·정리 확인
- 지휘가 방향별8자세·장비 손/시점·크기·8→1 경계 캡처 시각 검토, 독립 source/메타 검토 blocker 없음
- idle포함 머리 상단 proxy: FR0.15541·BR0.31194·BL0.35120·FL0.45795px. 실제 cap 픽셀이나 주관적 체감 전체를 보증하지 않음
- baseline 358978f의 S1 FR·모든idle·기존sources/PNG 보존, 각 방향은 직전 승인 커밋과 독립 비교
- four-direction-walk.mp4: 실제 fixture 프레임으로 만든960×960·30FPS·2초 확대4분할 미리보기. FFmpeg 전체 디코드 통과, 실측 FPS 근거가 아님
- 추가 사용자 요청의 [1주차 통합/성능 검수 결과](r1-week1-review.md): 실제 표시창30초·7,194프레임, native focus/재시작3회 통과

## 사용자 2차 확인

세 방향 적용·지휘 검수·커밋과 1주차 통합/성능 검수 완료, 사용자 실제 조작·체감 확인 대기

```powershell
.\.venv\Scripts\python.exe game/main.py
```

1. 네 방향 걷기의 발 교대·주기 이음새·몸/장비 크기 확인
2. 후진·옆걸음·마우스 방향 전환 시 보행 체감 확인
3. 정지/재출발·벽 접촉·다른 창 전환 뒤 입력 해제 확인

물리 키보드 확인 결과는 아직 미수신. 사용자2차·다음 진행 요청 전 R2 착수 금지, 푸시 미실행
