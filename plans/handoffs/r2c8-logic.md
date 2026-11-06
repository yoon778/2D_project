# R2-C8 로직 연결 인계 · 실제 1주차

기준선 `e23de0c`. 새 PNG14개/실제17소스 메타 인계 후 집중 회귀64개를 통과했으며 담당 파일을 동결했다.

- `CombatVisual`은 메타의 소스17개를 초기화 때 각각 한 번 로드한다. 기존 `attack`/`attack_walk` 이름과 `draw_attack(attack, foot_x, foot_y, walk_frame_index=None)` 인자를 유지한다.
- 저장된 `attack.facing`으로 정지/이동 소스를 선택한다. 지원하지 않는 방향·경과시간은 그리지 않는다. 보행 프레임0/None은 정지,1..8은 이동이다.
- main은 `select_facing` 결과를 공격 시작에 전달하며, 활성 공격의 저장된 각도로 표시한다. 실제 이동 변위만 기존 `PlayerVisual.update`에 전달하는 흐름을 보존했다.
- HUD/창 제목은 R2-C8·8방향 공격으로 갱신했다. smoke 출력은 `output/review/R2-C8/`를 사용한다.
- 기존 FR 전용 거절 기대값은 unknown 방향 거절과 back 방향 시작 허용으로 변경했다. 이미지 로드 fixture는 실제 메타 소스 수를 따른다.
- 생산 `combat.py`/`core.py`/`locomotion.py`/`player_visual.py`와 에셋은 수정하지 않았다. Git 작업도 수행하지 않았다.

## 최종 검증

- 실행: `.venv/Scripts/python.exe -B -m unittest game.tests.test_combat_directions_r2c8 game.tests.test_combat_visual_r2a game.tests.test_attack_walk_visual game.tests.test_visual_input_r1a game.tests.test_visual_title game.tests.test_attack_walk_logic game.tests.test_combat`
- 결과: 신규9개+영향55개, 총64개 통과. `Ran 64 tests in 16.154s`, 종료코드0. SDL queue 실행은 실제 메타/PNG를 사용했으며 방향 텍스처 대체 fixture는 적용하지 않았다.
- 새9개: 방향별 단계/보행 셀·발점 선택, 잘못된 방향/시간 거절,17소스 초기1회 로드·nearest·중간 캔버스 오류 정리, 실제 메타8방향 쌍 확인, SDL queue4개 회귀다.
- SDL queue는8방향 시작·저장 각도/방향·전후/옆 이동·벽/정지/재출발·회복 종료 위상·포커스/R·클릭 누름/해제를 검사한다. 기존 SDL dummy/software·고정dt·포커스 surrogate를 사용하며 실제 앱 루프/렌더/해제 경로를 통과했다.
- 생산 `combat.py`/`core.py`/`locomotion.py`/`player_visual.py`는 기준선 대비 diff가 없다. 검사 후 생산 코드 추가 수정은 없으며 Git 작업도 수행하지 않았다.
- 실제 Windows432상태·복귀 PNG/화면 비교·표시창 성능·사용자 물리 입력/주관적 모션 품질은 지휘 검수 범위다. 사용자 요청 범위의6단계×8보행을 유지한다.
