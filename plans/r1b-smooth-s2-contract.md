# 1주차 R1-B-S2 나머지 3방향 보행 개선

기준일: 2026-11-05 · baseline 358978f
사용자 직접 요청으로 back_right/back_left/front_left 모두 보행 8장 개선을 허용함
이 세 방향을 S2 한 묶음으로 처리하며 방향별 검수·수정·중간 커밋 후 다음 방향을 진행함
전체 세 방향 완료 후 사용자 2차 확인에서 정지. 이전 물리 키보드 검수 완료로 기록하지 않음

## 목표·순서

1. back_right(+pi/4): 뒤·오른쪽
2. back_left(+3pi/4): 뒤·왼쪽
3. front_left(-3pi/4): 앞·왼쪽

각 방향은 기존 idle 유지+실제 보행 8장. front_right의 기존 S1 전체 9프레임·소스 PNG·메타는 정확히 보존
최종 네 방향 모두 idle1+walk8, 총36자세. 방향 자체는 4개이며 8방향 회전 기능을 뜻하지 않음
90px/s·32px 주기·실제 거리 위상·마우스 facing·5도 여유·이동/충돌/입력/종료 유지
왼손 몸 앞 택배·오른손 방망이·가슴등의 해부학적 손, 도트풍 고정 사선 유지
전투·좀비·빛·새 UI·속도/주기 튜닝·R2 미착수

## 담당

| 담당 | 변경 가능 |
| --- | --- |
| 로직 채팅 | game/tests/test_locomotion*.py, plans/handoffs/r1b-smooth-s2-logic.md. 실제 오류가 있을 때만 game/locomotion.py |
| UI·에셋 채팅 | game/assets/player/r1b-smooth-{back-right,back-left,front-left}-20261105.png/.prompt.txt, 기존 atlas JSON, game/tests/test_visual*.py, 필요한 player_visual.py 연결 수정, 자기 handoff |
| 지휘 | 계약·공용 진행 문서·검수·수정 요청·Git |

기존 순수 API가 이미 N장 지원하므로 로직을 억지로 바꾸거나 새 시스템을 만들지 않음
core.py·main의 입력/루프·기존 PNG/프롬프트·기존 idle·S1 front_right 변경 금지
Git은 지휘만 담당. 사용자 별도 업로드 요청 전 푸시 금지

## 로직 검수

기존 Locomotion.walk_frame_index(N), PlayerVisual.frame_index 재사용
8장 상태에서 4방향 전환 후 phase 보존·실제 거리·후진/옆걸음·벽 정지·프레임 경계·idle 복귀 집중 확인
프로젝트의 실제 API·의미 있는 동작만 테스트. 기존 검증을 줄이거나 UI 파일을 변경하지 않음
UI 구현과 독립 검수 후 자기 보고서 작성·정지

## 에셋·단계별 통합

한 방향당 4열×2행의 투명 보행 sheet, 시간순8자세·양발 접촉/하강/통과/상승·마지막→처음 연결
기존 해당 방향/기존 S1 그림을 view_image한 뒤 imagegen 스킬·내장 imagegen 사용
방향마다 1회 생성·검수 후 실제 오류만 표적 교정. 전체 회전/반전·동일 자세 복제·상하 이동·크로스페이드로 중간 자세를 만들지 않음
뒤쪽 방향에서 가방·모자 뒷면이 보이고 상자/가슴등은 시점에 따라 자연스럽게 가려짐
한 sheet에 고정 배율 하나·공통 몸 기준 root, 프레임별 bbox128px 정규화 금지
기존 해당 idle과 머리/흉부/가방 크기 정렬. 머리 상단 높이 차이3px 이내는 보조 지표, 실제 자세는 별도 시각 검수
실제 해상도·셀 정수 경계·clip/root·고정 ref height·SHA256·정확 프롬프트·출처·알파/생성 한계 기록

atlas JSON sources에 새 소스 추가, 해당 방향 frames만 idle+8walk로 연결
다른 방향과 기존 sources 사전/PNG는 보존. 모든 소스 nearest/canvas/종료 정리 확인
테스트는 중간 상태(일부만8장)를 지원하며 이미 확장한 방향은8장·대기 방향은기존2장 검사
최종 세 방향 연결 시 네 방향 모두8장임을 검사. 기존 S1 front_right·모든idle 보존 회귀 유지

UI는 방향1개 생성·연결·집중검사·dummy contact sheet 후 **방향별 보고하고 정지**
지휘가 실제 PNG·네이티브 렌더·중간 커밋을 확인한 뒤 다음 방향 착수 지시
사용자의 세 방향 전체 요청이 이 내부 진행을 허용함. 방향 사이 사용자 추가 승인을 요구하지 않음
최종 handoff plans/handoffs/r1b-smooth-s2-ui.md에 방향별 생성/수정/증거/한계 누적 기록
UI는 dummy 렌더만, 네이티브/GUI 조작 금지

## 지휘·사용자 검수

- 방향마다 원본 8자세·반대 발 전진·장비 손·앞/등 방향·고정 크기/root·8→1 경계 검토
- 숨김 Windows SDL 실제 렌더, 4방향 모두 actual distance 2초/60프레임 시퀀스·프레임 선택/정지/가림 회귀
- 전체 자동 검사·compileall·리소스 정리·기존 S1/idle/baseline 보존 확인
- 순서별 캡처 검토와 사용자 물리 키보드·실제 연속 보행 체감은 구분
- 사용자2차: 4방향 걷기·후진/옆걸음·정지/재출발·발 움직임·몸/장비 크기 확인

커밋 `<type>: 1주차 R1-B-S2 <한글 설명>` 실제 날짜·의미 있는 검증 단위마다 기록
사용자2차 확인과 다음 진행 요청 전 R2·추가 방향 확장 미착수
