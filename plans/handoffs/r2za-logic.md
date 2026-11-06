# R2-ZA 좀비 공격 로직 인계 · 실제 1주차

기준선 `450f3a1`. 판정31개·실제 공격 PNG/JSON 인계 후 시각 영향48개 검사 통과, 담당 코드 전체를 동결했다. 이미지 최종 동결/시각 품질은 지휘 확인 범위다.

## 판정

- `Zombie.attack`과 `ZombieAttack(angle, facing, elapsed=0, _hit_done=False)`를 추가했다. 상수는 `ZOMBIE_ATTACK_DURATION=.8`, `ZOMBIE_ATTACK_HIT_TIME=.3`이다.
- 중심 거리28px에서 방향/각도를 고정해 공격한다. 준비·타격·회복 동안 제자리이며 .30초에 거리/±50도/벽/무적을 재검사해 피해1을 한 번 적용한다. 헛공격은 다시 판정하지 않는다.
- 플레이어 타격·좀비 경직/사망·승패는 진행 중 좀비 공격을 취소한다. 플레이어 단일 타격/공격 시간·HP·무적·이동 속도·경직 시간은 유지했다.
- 1ms 최대 tick을 유지하고 플레이어/좀비 공격·경직·무적 경계에서 tick을 나눈다. 추격이 접촉 거리에 도달한 뒤의 잔여 시간도 공격에 전달한다. 회복 종료 뒤 다음 내부 tick에서 재공격/추격하므로 외부 update 호출 크기에 따른 추가 쿨다운은 없다.
- 판정 동결 파일: `game/combat.py`, `game/tests/test_combat.py`, `game/tests/test_attack_walk_logic.py`, `game/tests/test_zombie_attack_logic_r2za.py`. 중간 커밋은 지휘 담당이다.

## 시각/입력

- 새 모듈 상수 `combat_visual.ZOMBIE_ATTACK_METADATA_PATH`를 새 공격 JSON에 연결한다. 메모리 메타에 `zombie_attack`을 추가하며 해당 JSON.parent 기준 PNG를 초기화 때 한 번 로드한다. 기존 소스는 유지해 총47이미지 구조다.
- `_zombie_pose(zombie)`가 현재 소스명/frame을 함께 반환하며 draw/opaque 픽킹이 공유한다. 사망→피격→잠긴 공격 facing/elapsed→보행/정지 순서다. 기존 `_zombie_frame`·공개 좀비 API도 유지한다.
- 공격 동안 보행 표시는 중지하고 위상은 보존한다. 실제 변위는 기존 Locomotion에 전달하며 공격 종료 뒤 같은 위상에서 이어간다. 별도 시각 타이머는 없다.
- main 모듈 설명·창 제목/HUD를 R2-ZA로 갱신했고 입력 안내는 유지했다. R은 월드 공격/시각 상태를 초기화하며 이미지를 재로드하지 않는다.
- 기존 R2-Z105상태·플레이어·기존 전투JSON/PNG·core/locomotion/player_visual·Git은 수정하지 않았다. 제품 스텁도 생성하지 않았다.

## 최종 검증

- 순수 판정/보행31개 통과: 기존24개+새 판정7개. 8방향 준비/타격/회복·거리 회피/각도/벽·무적·동시 타격 우선·경직/사망 취소·dt0/R/승패를 포함한다.
- 시간 분할은 단일 update/.05/.016/.01/1/60/1/240/.0173/불규칙 순환을 검사했다. 검사한 정지 추격/일직선 회피/플레이어 반격 사례의 HP·위치·공격/무적/경직 상태는 소수8자리까지 일치했다.
- 지휘 probe 사례(p480,180/z540,180, 벽 없음, 총1.2초)의 다음 공격 경과시간은 약.0444444444445초다.6개 분할의 최대 차이4.043987367197133e-14초. 수치는 `output/review/R2-ZA-logic/time-partition-probe.json`에 기록했다.
- 메모리 공격 메타/mock draw로 시각/메타 영향22개 통과. 새 시각 검사5개는64상태 소스/발점/현재alpha·우선순위/위상 복귀와 실제 SDL queue의 준비/타격/회복·회피/포커스/R·플레이어 타격 취소를 검사한다.
- 실제 에셋 인계 후 `.venv/Scripts/python.exe -B -m unittest game.tests.test_zombie_attack_visual_r2za game.tests.test_zombie_visual_r2z game.tests.test_combat_visual_r2a game.tests.test_attack_walk_visual game.tests.test_combat_directions_r2c8 game.tests.test_visual_title`의48개를1회 실행했다.
- 결과: `Ran 48 tests in 22.425s`, `OK`, 종료코드0. SDL queue 실행은 실제 새 공격/기존 좀비/플레이어 PNG·메타를 사용했고 대체 텍스처/메타 fixture는 적용하지 않았다. 단위 상태/소스/alpha 검사는 별도 메모리 fixture/mock draw를 사용한다.
- 실제 SDL queue에서 준비 무피해·.30 단일 피해·8시각 단계·회복 종료/재공격·제자리·회피·포커스/R·플레이어 타격 취소·피격 소스 전환을 확인했다. 기존 SDL dummy/software·고정dt·포커스 surrogate와 실제 앱 루프/그리기/종료 정리 경로를 사용했다.
- 초기 이미지47개·프레임/R 추가 로드0 검사도 통과했다. 실행 로그는 `output/review/R2-ZA-logic/actual-source-tests.txt`, 검사 직후 리소스 스냅샷은 같은 폴더 `actual-source-snapshot.json`이다.
- 실제 검사 후 생산 코드 추가 수정·에셋 수정·Git 작업은 없었다. 신규 판정7개+시각/queue5개를 추가했고 나머지 기존 기대값 변경은 명시 공격/추가1텍스처/단계명 충돌에 한정했다.
- 전체 회귀·실제 Windows64공격상태/8방향 실공격/회피/취소/복귀·표시창 성능/자원·물리 입력/체감은 지휘 검수 범위다.
