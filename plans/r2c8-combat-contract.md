# R2-C8 8방향 이동 공격 · 2026-11-06

사용자 승인: 나머지7방향 공격 모션·이동 보행 연결·두 채팅 지시·게임 적용·지휘 검수·중간 커밋
기준선 `e23de0c`, 현재1주차. 기존 front_right54자세와R1 전체를 보존하고 나머지7방향을 확장함

## 담당

- UI·에셋: 새 `art/player/r2c8-combat-assets.cjs`와 전용 설정/검사, 기존 전투 JSON에 새 소스14개 추가, 새7방향 정지/이동 PNG14개. `plans/handoffs/r2c8-ui.md` 보고
- 지휘 추가 허용: 기존 `r2a-combat-assets.cjs`는 JSON 추가 키 보존만 보완해 새14소스를 삭제하지 않게 함. 원본 PNG/기존3메타 값은 유지
- 로직: `game/combat_visual.py`·`game/main.py`, 관련 Python 검사·새 방향 검사. `plans/handoffs/r2c8-logic.md` 보고
- 지휘: 이 계약·통합/실제SDL·성능·문서·Git. 두 채팅은 담당 밖 수정/Git 금지
- 기존 core/locomotion/player_visual/combat.py·R1 원화/부품/메타/PNG·FR 공격/이동 PNG·좀비PNG 불변

## 공통 API

- 방향명: `front_right,right,back_right,back,back_left,left,front_left,front`
- runtime 각도: right0, back_rightπ/4, backπ/2, back_left3π/4, leftπ, front_left−3π/4, front−π/2, front_right−π/4
- 원화/rig의 화면y와 runtime 지면y 부호를 혼동하지 않음. 몸 전체 회전/미러로 방향을 만들지 않음
- 기존 JSON top-level `attack,zombie,attack_walk` 블록 그대로 유지
- 새 각 방향 `facing`마다 top-level `attack_<facing>`·`attack_walk_<facing>` 추가. 모두 image/canvas_size/facing/cell_size/scale/reference_height/frames 형식 유지
- 파일: `r2c8-attack-<hyphen-facing>-20261106.png`(288×192), `r2c8-attack-walk-<hyphen-facing>-20261106.png`(768×576)
- 정지6장(96셀3×2), 이동6×8장(96셀8×6), 피벗(48,80)·기준신체64·2배nearest·alpha0/255·승인팔레트 유지
- 정지frames는 기존attack의name/label/start/end/clip/pivot 형식. 모든 방향 같은 경계0/.09/.18/.27/.37/.48/.60초
- 이동frames는 attack_index0..5, walk_frame_index1..8, clip/pivot. 인덱스=attack_index×8+walk−1
- `CombatVisual.draw_attack(attack,foot_x,foot_y,walk_frame_index=None)` 유지. 방향으로 소스 선택,0/None은 정지,1..8은 이동. 지원하지 않는 방향/경과시간은 False
- CombatVisual은 메타 소스를 시작 때1회 로드, 프레임 중 이미지 생성/파일로드 금지. 원래FR 소스명 유지
- main의 FR 시작 제한만 해제해 select_facing 결과를 start_attack에 전달. 공격 중 저장한 facing/angle 유지, 재클릭/포커스/R 동작·실제거리 보행 위상 불변
- 렌더와 판정이 같은 공격각을 사용. 0.6초 공격/0.18초 단일 타격·90/60px/s·stride64·5타/0.4초 경직·HP3 유지

## 에셋

- 승인한 방향별 원화/부품을 재사용해 오른팔/손/방망이만 관절로 움직임. 왼손 택배·가방·머리·체형·팔 길이 유지
- 모든 방향 준비→타격→후속→회복→복귀. 타격 시 무기가 해당 조준 쪽으로 뻗어야 함
- 가려진 다리는 기존 전체 다리 부품/관절로 복원. 최종그림에서 무기만 지워 다리 구멍을 남기지 않음
- 뒤/왼쪽의 오른팔·방망이는 실제 몸 깊이에 따라 부분 가림. 전 프레임 무기 전체 삭제 금지
- 이동은 기존 양발8위상·1px bob 사용. 각 방향 마지막 복귀8장은 해당 R1 걷기PNG의(8,8) 패딩과 RGBA 일치. 정지 마지막은 해당 R1 idle과 일치
- 새 제작명령은14소스 모두 재현하고 기존FR/좀비/메타3블록을 보존. require/import가 기존 베이크를 실행하지 않음
- R1 helper 추가 export가 필요하면 먼저 지휘에 보고, 알고리즘 수정/기존 에셋 재생성 금지

## 검수·인계

1. UI는 먼저7방향 정지6장 비교시트·타격8보행 시트 제출, 가림/그립 검수 뒤 필요한 수정
2. 로직은 실제SDL queue로8방향 공격 시작·방향 잠금·멈춤/벽/재출발·종료 위상·포커스/R/누름반복 검증. FR-only 옛 검사만 새 요구에 맞게 갱신
3. 지휘는 실제PNG 규격/불변/복귀RGBA,8방향정지48+이동384상태·전후옆걸음 캡처, 표시창 실제시간/자원 측정
4. 방향/그립/발/깊이/셀 잘림 이상은 담당에 수정 요청하고 영향 재검수
5. 통과한 단위로 실제1주차 한국어 커밋·weekly 로그. 다음 기능/R3는 구현하지 않고 사용자2차 확인에서 정지
