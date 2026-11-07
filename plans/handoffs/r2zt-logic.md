# R2-ZT 공격 진입과 보행 복귀 · 실제 1주차

기준선 `b6a0a0f`. 동결된 복귀 PNG/JSON으로 영향 검사 28개를 통과했으며 담당 파일을 동결했다.

- 공격 객체가 처음 보일 때 직전 표시 방향을 기준으로 `select_facing`을 호출한다. 초기화 전에는 `attack.facing`을 사용한다. 같은 공격 객체는 표시 방향을 유지하고, 물리 공격각은 기존 판정에 그대로 전달된다.
- 관찰한 공격 객체가 `.80`초에 정상 종료하면 복귀를 대기한다. 첫 이동 직전 위상에 `8/64`를 더한 걷기 인덱스를 고르고 실제 이동 0~4px, 4~8px 구간에 두 복귀 프레임을 적용한다. 8px부터 기존 보행이며 실제 거리 누적은 기존 `Locomotion`이 담당한다.
- 실제 정지는 idle로 복귀한다. 포커스 정지 중에는 현재 복귀 프레임과 거리/위상을 유지한다. main의 `paused=not active` 연결로 둘을 구별한다. 피격/사망/새 공격/R은 복귀를 초기화한다. 복귀 프레임이 없는 메타는 기존 보행을 사용한다.
- `_zombie_pose`가 그리기와 픽킹에 같은 프레임을 제공한다. PNG의 새 행도 기존 좀비 텍스처에서 읽는다.

## 검증

- 기존 코드에서 25도 접근 시 walking right → attack back_right 재현 확인. 변경 후 새 fixture 7개와 기존 판정/시각 14개, 총21개 통과했다.
- 검사 범위는 공격 객체별 잠금, 정상 종료/취소, 첫4/8px·위상 wrap·동일 update의 회복/이동, 포커스 정지/재개, 실제 정지, 피격/사망/R/새 공격, 현재 alpha, 기존 메타 fallback이다.
- 실제 리소스 인계 후 `.venv/Scripts/python.exe -B -m unittest game.tests.test_zombie_transition_r2zt game.tests.test_zombie_attack_logic_r2za game.tests.test_zombie_visual_r2z game.tests.test_zombie_attack_visual_r2za`를 1회 실행했다. `Ran 28 tests in 3.022s`, `OK`, 종료코드 0이다.
- 실제 소스를 사용한 SDL queue에서 정상 회복 뒤 두 복귀 행, 포커스 정지 중 같은 행·위상, 재개 후 일반 보행 연결을 확인했다. 기존 SDL dummy/software·고정dt·합성 포커스를 사용했다.
- 실제 Windows 렌더/성능·전체 회귀·Git은 지휘 담당이다.
