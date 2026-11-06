# R2-Z 좀비 도트·걷기·피격 · 2026-11-06

사용자 승인: 좀비를 주인공과 같은 도트풍으로 제작·걷기/피격 적용·두 채팅 지시·검수·중간 커밋
기준선 `e85cc07`, 실제1주차. 좀비1종/1마리 범위, 플레이어와 전투 규칙 보존

## 담당

- 지휘: 기준 원화/스타일 입력 제공·계약·통합/실제SDL/성능·문서·Git
- UI·에셋: 새 `art/zombie/` 제작/검사/설정·원화/부품, `game/assets/zombie/r2z-zombie-20261106.png`와 같은 이름 JSON. `plans/handoffs/r2z-ui.md` 보고
- 로직: `game/combat_visual.py`·`game/main.py`, 필요하면 작은 `game/zombie_visual.py`·관련 Python 검사. `plans/handoffs/r2z-logic.md` 보고
- 두 채팅은 담당 밖 수정/Git 금지. core/combat/locomotion/player_visual·플레이어 원화/부품/PNG·기존 전투JSON/PNG 보존

## 원화와 규격

- 지휘가 imagegen 기준 원화를 새 zombie 폴더에 제공. UI는 현재 승인한 플레이어/rig의 카메라·체형·질감도 함께 읽고 최종 게임 도트를 제작. 새 원화 입력 전에는 준비/제작 코드만 진행, 임시 사각형을 최종으로 대체하지 않음
- 고정 사선3/4·native64px 기준·80셀·발점(40,72)·2배nearest·alpha0/255·24색 이내. 방향별 키/체형을 임의로 세로압축하지 않음
- 동일한 성인 좀비1종: 창백한 회녹 피부·낡은 저채도 옷·두꺼운 어두운 윤곽/단계 음영. 주인공과 같은 신체/도트 밀도, 좀비는 구부정한 자세로 구별. 택배/방망이/가방/모자 없음
- 방향 순서 `front,front_right,right,back_right,back,back_left,left,front_left`. 전체 몸 회전/미러로 다른 방향을 만들지 않음
- 방향당 idle1·보행8·피격4,105상태(8×13+단일 corpse1). 피격 마지막은 idle로 복귀해 중복 가능, 보행8/피격4는 각 상태 안에서 고유
- PNG640×1120: 80셀8열14행. row0 idle8, row1..8 보행각위상8방향, row9..12 피격각단계8방향, row13 col0 단일 corpse. 남은7셀 투명
- 사망은 기존처럼 단일 정지 자세만 같은 좀비 모습으로 연결, 새 사망 애니메이션/공격 모션/새 AI는 범위 밖
- 첫8방향idle/주인공 비교·보행/피격 시트부터 빠르게 저장, 모션은 일관된 원화와 실제 부품을 기반으로 반복 교정

## 새 JSON/API

- 새 JSON top `image,canvas_size,cell_size,scale,reference_height,stride_distance,facings,frames`
- image는 JSON과 같은 폴더의 PNG 파일명, canvas_size[640,1120],cell_size[80,80],scale2,reference_height64,stride_distance64
- facings[name]는 `idle` 단일frame·`walk`8frame·`hit`4frame 배열. frames.dead는 corpse frame
- 모든frame은 `clip_topleft`·아틀라스 절대 `foot_pivot_topleft`·해당 셀 alpha의 정확한 `opaque_rows`(문자열row→[[left,right],...]) 포함
- hit frames는 start/end초:0/.06/.14/.26/.40. 마지막(.26~.40)은 같은방향idle RGBA로 정착. 모든 피격 셀의 지면 발점 고정
- CombatVisual은 기존 전투JSON의 플레이어16소스를 그대로 사용하고 zombie만 새 JSON으로 읽어 대체. 경로 기준은 새JSON.parent, 기존 전투JSON 자체는 바꾸지 않음
- 기존 draw_zombie(zombie,foot_x,foot_y)/zombie_contains(...)/close API 유지. 신규 update_zombie(zombie,dx,dy)·reset_zombie_animation()로 실제 이동 변위/초기화 연결
- 위치는 main에서 world.update 전후의 실제 zombie x/y 차이만 전달. 기존 Locomotion/방향 선택 재사용 가능, 새 벽시계 보행 타이머/걷기 시작 때 phase reset 금지
- hit 시간은 STUN_DURATION−stun_remaining에서 선택,별도물리타이머/넉백 추가 금지. 정지/벽/피격 동안 보행위상 유지,경직 해제 후 이동 거리로 재개
- 현재 선택한 방향/보행/피격 frame의 opaque_rows로 몸 클릭,투명 여백은 지면 조준. 죽으면 클릭대상 제외
- R은 새 시각 상태도 초기화하되 텍스처 재로드 없음. 시작에 새좀비1텍스처를 로드해 기존 임시 좀비 텍스처를 대체, 프레임 중 파일/이미지 생성 금지. close에서 참조/SDL 자원 해제
- HP5·90px/s·0.4초 경직·제자리 유지·플레이어 공격0.6/.18·접촉/무적/승패 규칙은 불변

## 검수

1. 원화/카메라/체형·팔레트·알파·8방향 일관성, 양발 교대·피격 읽힘·그림 고립/잘림 확인
2. 실제 변위·정지/벽/피격/복귀·재피격/5타 사망·방향/상태별 정확한 opaque 픽킹·포커스/R/해제 검사
3. 지휘 실제 Windows105상태·시간순 추격/경직/재출발·발점/원본 보존, 표시창 실시간 성능/자원 검수
4. 의미 있는 검증 단위의 실제1주차 커밋·weekly 로그, 지휘1차 수정/검수 후 사용자2차 확인에서 정지
