# R2-ZA 좀비 공격 · 2026-11-06

사용자 승인: 좀비 공격 모션 제작·두 채팅 지시·게임 적용·검수/수정·중간 커밋
기준선 `450f3a1`, 실제1주차. 기존 좀비1종/1마리·도트풍 유지

## 담당/보존

- UI·에셋: 새 `art/zombie/r2za-*` 제작설정/스크립트/부품/검사, `game/assets/zombie/r2za-zombie-attack-20261106.png`/JSON, `plans/handoffs/r2za-ui.md`
- 로직: `game/combat.py`·`game/combat_visual.py`·`game/main.py`와 관련 Python 테스트, `plans/handoffs/r2za-logic.md`
- 지휘: 계약·독립 코드/실제Windows/성능/시각 검수·수정요청·문서·Git
- 기존 R2-Z 105상태 PNG/JSON·원화/정규화/기존rig/부품/제작스크립트·플레이어 전부·기존 game/assets/combat/·core.py/locomotion.py/player_visual.py 보존. 기존 검사 중 새 명시 공격/추가1텍스처와 충돌하는 기대값만 갱신
- 새 AI/소음/길찾기/맵/손전등/다수좀비/사망 모션 추가 금지. 기존 두 채팅만 사용, 담당 밖 편집/Git 금지

## 공격 판정

- `Zombie.attack: ZombieAttack | None`, `ZombieAttack(angle,facing,elapsed=0,_hit_done=False)`. 기존 플레이어Attack과 별개
- 접촉 즉시 피해를 좀비의 준비→타격1회→회복으로 대체. 전체0.8초·타격0.30초, 시작/타격 거리28px(기존2*PLAYER_RADIUS), 타격 전방±50도·지면 벽 차단
- 공격 시작 순간 atan2로 대상 방향/angle/facing 잠금, 제자리에서 준비/타격/회복. 공격 중 상대를 따라 회전하거나 이동하지 않음
- 타격 순간 살아 있는/경직 없는 좀비가 플레이어 거리·방향·벽을 재검사. 벗어나면 헛공격이며 이후 해당 공격의 추가 피해 없음. 피해1·플레이어HP3/피격무적1초 유지, 무적 중에도 공격 모션은 정상 재생
- 공격 종료 뒤 다음 tick부터 기존 추격/다음 공격. 외부 update 호출의 분할 크기로 공격 간격이 달라지지 않게 잔여 시간을 보존, 별도 추가 쿨다운/잡기/밀기 없음
- 플레이어 타격/경직/좀비 사망을 우선 처리, 진행 중 좀비 공격 즉시 취소. 취소한 공격의 지연 피해 없음. 승패/R에서 공격 상태 초기화, dt0/포커스 정지 때 시간도 정지
- 기존 플레이어 공격0.6초/타격0.18초·이동90/공격중60·좀비90/HP5·제자리경직0.4·벽/승패 판정 보존. 기존1ms 분할 tick에서 시간분할 일관성 유지

## 공격 에셋/연결

- 기존 승인 좀비 native64/80셀/발점(40,72)/정수2배nearest/24색·alpha0/255 유지. 기존8방향 원화에서 같은 몸/팔 재질·관절로 제작, 전신 회전/미러/방향별 세로압축 금지
- 방향 순서 front/front_right/right/back_right/back/back_left/left/front_left
- 8방향×8자세=64셀. PNG640×640, 열=방향/행=공격단계0..7. 발바닥 고정·준비/팔 뻗기/접촉/회수 가독성·깊이에 따른 팔 가림, 셀 잘림/고립 픽셀 검수
- 프레임 경계0/.08/.16/.30/.40/.52/.64/.72/.80초. 마지막 .72~.80은 같은 방향 R2-Z idle RGBA 동일. 방향별8자세 고유
- 새JSON top `image,canvas_size,cell_size,scale,reference_height,facings`. facings[name]는8개 frame 배열. frame은 `clip_topleft,foot_pivot_topleft,opaque_rows,start,end`. alpha 마스크는 셀별 실제PNG와 정확히 일치
- CombatVisual의 메모리 메타에 `zombie_attack` 소스1개 추가. 새JSON.parent 상대경로. 기존 좀비/플레이어 소스는 변경 없음. 초기 이미지47/폰트1, 프레임/재시작 재로드 없음
- 선택 우선순위 사망→피격→공격→걷기/정지. ZombieAttack.facing/elapsed로 공격 소스 선택. 현재 소스/프레임을 draw와 opaque picking에서 공유
- 기존 draw_zombie/update_zombie/reset_zombie_animation/zombie_contains API 유지. 실제 이동 거리의 gait phase 보존, 공격 동안 걷기 표시는 중지. 복귀는 같은 위상에서 재개
- main 창제목/HUD를 R2-ZA로 식별, 기존 입력 유지

## 검수/인계

1. UI는 FR 한 방향 공격8장 먼저 시트로 알림, 지휘 팔·체형·접지 검토 후 나머지7방향. 전체64셀/idle복귀8/팔 연결·팔레트/잘림/정확alpha/기존파일불변·임시폴더재현 검사
2. 로직은 준비 중 무피해/타격1회/회복/거리회피/각도잠금/벽/무적/피격취소/사망/동시우선/R/dt0·분할시간·현재alpha/R/로드·해제 검사. 실제 리소스 도착 전 테스트fixture만 허용
3. 지휘 전체 회귀·실제Windows64공격상태/시각검수/8방향 실공격·회피/취소/복귀/표시창 실시간 성능·자원 검수. 물리 키보드/체감과 자동 검수 구분
4. 실제1주차 한국어 Conventional Commit·주간로그. 지휘1차 검수/수정/커밋 뒤 사용자2차 확인에서 정지
