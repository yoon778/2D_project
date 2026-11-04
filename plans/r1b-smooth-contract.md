# 1주차 R1-B-S1 한 방향 보행 개선

기준일: 2026-11-05
사용자 한 방향 보행 개선·두 채팅 지시·게임 적용·검수·중간 커밋 요청으로 착수
기존 R1-B 사용자 물리 키보드 검수 완료를 뜻하지 않음
이번 묶음의 지휘 검수·수정·커밋 후 사용자 2차 확인에서 정지

## 범위와 소유권

- front_right(-pi/4) 한 방향만 idle 1장+실제 보행 8장으로 개선
- 다른 세 방향은 기존 idle+보행 2장 유지, 기존 방향 선택·조준·이동/충돌 유지
- 이동 90px/s·보행 한 주기 32 지면 px 유지, 실제 변위로 위상 진행
- 몸 앞 왼손 택배·오른손 방망이·가슴등·도트풍 고정 사선 유지
- 전투·좀비·다른 방향 확장·8방향·시야·새 UI/메뉴·R2는 미착수

| 담당 | 변경 가능 |
| --- | --- |
| 로직 채팅 | game/locomotion.py, game/tests/test_locomotion*.py, plans/handoffs/r1b-smooth-logic.md |
| UI·에셋 채팅 | game/player_visual.py, game/main.py 안내 문구, game/assets/player/r1b-smooth-*, 기존 r1b-courier-atlas-20261104.json, game/tests/test_visual*.py, plans/handoffs/r1b-smooth-ui.md |
| 지휘 | 공용 문서·연결 계약·독립 검수·수정 요청·Git |

core.py·기존 PNG·기존 프롬프트·다른 방향의 그림/배율/발점 변경 금지
기존 JSON의 sources에 새 소스 추가하고 front_right frames만 idle 유지+보행 8장으로 변경
Git 조작은 지휘만 수행, 푸시는 별도 업로드 요청 때만 수행

## 연결 API

Locomotion에 순수 `walk_frame_index(frame_count: int) -> int` 추가
정지 0, 이동은 위상 [0,1)을 frame_count 등분하여 1..frame_count 선택
양의 정수 아닌 frame_count는 ValueError. 2장/8장·정확 경계·거리 분할/FPS 독립 검사
기존 frame_index 속성은 2장 기준 호환 유지, 실제 위상·방향·32px 주기는 그대로 유지
호출로 위상·방향·이동 상태를 변경하지 않음

PlayerVisual.frame_index 읽기 전용 속성은 현재 방향 `len(frames)-1`을 위 메서드에 전달
draw도 이 속성을 사용. 실제 선택을 검증하는 UI 테스트는 이 속성을 관찰
기존 main의 update/실제 변위 연결·SDL 입력/포커스/종료는 유지
프레임 수에 따라 루프 속도나 이동 속도를 바꾸지 않음

## 에셋

내장 imagegen·imagegen 스킬로 기존 캐릭터 참조 후 보행 8자세 투명 sheet 제작
4열×2행, 좌상단부터 시간순 0/8..7/8 위상. 실제 좌우 발 교대·접촉/하강/통과/상승 중간 자세
frame1~4는 한 발, frame5~8은 반대 발의 대응 반주기. 마지막과 처음도 이어지는 자세
우선 1회 제작·검수, 실제 오류에만 표적 수정. 동일 자세 복제·크로스페이드·전체 상하 이동으로 중간 자세를 대신하지 않음
기존 idle은 유지. 새 보행 sheet 전체에 고정 배율 하나를 사용하고 프레임별 bbox 정규화 금지
같은 몸 기준 root·머리/흉부 크기·택배/방망이 손 고정, 팔은 장비를 든 자세 유지
새 파일 r1b-smooth-front-right-20261105.png/.prompt.txt. 소스별 canvas/clip/pivot/cell/SHA256·정확 입력·실제 해상도·출처 기록
출력은 정확한 64px 원본 격자라고 주장하지 않음. 모든 소스 nearest·크기 검사·오류/종료 정리 유지
프로그램으로 PNG 그림 편집 금지, 알파/기하 읽기 분석·게임 runtime clip/render는 허용
메타 scale_reference_height는 새 sheet의 모든 프레임에서 동일, 머리·상체 기준으로 idle과 크기 정렬

## 검수·인계

- 로직: 2/8장 선택·경계·정지·방향 변경 위상 보존·무효 입력·거리 분할 검사
- UI: 새 8장 실제 셀·소스/clip/root·공통 배율·frame_count 선택·자원 정리, 다른 3방향 유지 검사
- 지휘: 전체 회귀·실제 Windows SDL 숨김 렌더·시간순 보행 연속 영상/프레임 검토·벽 앞 idle/포커스·다른 방향 회귀
- 8장이 서로 실제 중간 다리 자세인지, 좌우 발 교대와 주기 이음새·머리/몸/택배 크기·발 미끄러짐을 시각 검토
- 머리 높이 차이 3px 이내는 보조 수치, 실제 부드러움 판정과 구분
- 사용자: 실제 WASD·마우스·보행 체감·외형을 2차 확인, 이후 다음 범위 결정

UI는 dummy 렌더만 사용, 네이티브/GUI 창 조작은 지휘 담당. 지휘도 사용자 화면 방해를 피해 숨김 창 검수
각자 자기 handoff에 실제 명령·결과·한계 기록 후 정지. 다음 단계·Git 조작 금지
커밋 `<type>: 1주차 R1-B-S1 <한글 설명>`으로 의미 있는 검증 단위마다 기록
