# R2-Z 로직 연결 인계 · 실제 1주차

기준선 `e85cc07`. 실제 새 좀비 PNG/JSON 인계 후 영향43개 검사 통과, 담당 코드를 동결했다.

## 연결

- 모듈 상수 `combat_visual.ZOMBIE_METADATA_PATH`가 `game/assets/zombie/r2z-zombie-20261106.json`을 가리킨다. 초기화 때 기존 전투JSON을 읽고 메모리의 `zombie`만 새 JSON으로 대체한다. 새 이미지 경로는 새 JSON.parent 기준이다.
- 기존 플레이어16소스/임시좀비 JSON·PNG는 수정하지 않는다. 기존좀비를 로드하지 않고 새좀비1텍스처로 대체하므로 전투17개/전체46개 초기 이미지 로드 구조를 유지한다.
- `update_zombie(zombie, dx, dy)`는 기존 `Locomotion`을 사용한다. 방향은 기존 좀비 aim_angle, 보행 위상은 실제 이동 거리/stride64를 따른다. 공격에 맞기 전 같은 프레임에 이미 이동한 거리도 보존한다.
- 피격은 별도 시계 없이 `STUN_DURATION - stun_remaining`과 메타 end 경계로4단계를 선택한다. 정지/벽/경직은 위상을 유지하고 재출발은 실제 거리에서 이어간다. 죽으면 단일 `frames.dead`만 표시한다.
- `_zombie_frame(zombie)`의 현재 frame을 그리기와 opaque 픽킹이 공유한다. 죽은 좀비는 픽킹에서 제외한다.
- main은 world.update 전후의 좀비 x/y 차이를 전달한다. R은 `reset_zombie_animation()`으로 초기화한 후 같은 프레임의 실제 추격 이동량만 다시 누적한다. 텍스처 재로드는 없다.
- 지휘 요청으로 main의 모듈 설명·창 제목·HUD 단계명을 R2-Z로 갱신했다. 입력 안내·전투 동작은 유지한다.
- core/combat/locomotion/player_visual·플레이어/기존 전투 리소스·Git은 변경하지 않았다. 별도 zombie_visual.py는 만들지 않았다.

## 최종 검증

- 실제 에셋 인계 후 `.venv/Scripts/python.exe -B -m unittest game.tests.test_zombie_visual_r2z game.tests.test_combat_visual_r2a game.tests.test_attack_walk_visual game.tests.test_combat_directions_r2c8 game.tests.test_visual_title`를1회 실행했다.
- 결과: `Ran 43 tests in 20.726s`, `OK`, 종료코드0. 기존 영향32개+신규7개+제목4개다. SDL queue 실행은 실제 새 좀비/플레이어 PNG와 메타를 사용했으며 대체 텍스처/메타 fixture를 적용하지 않았다.
- 신규 순수 상태4개는 테스트 메타/mock draw로 실제 CombatWorld8방향/8보행·정지/재출발,4피격 경계/재피격/5타 corpse,105상태의 현재 mask/발점,17소스 overlay/경로/초기화/참조 해제를 확인한다.
- 새 SDL queue3개는 추격/포커스/R·초기46로드/추가로드0, 벽 정지/위상 보존, 실제 피격4단계 후 추격 재개를 통과했다. 기존 SDL dummy/software·고정dt·포커스 surrogate를 사용하며 실제 앱 루프/그리기/종료 정리 경로를 통과했다.
- 검사 후 생산 코드 추가 수정·에셋 변경·Git 작업은 없었다. 제품 메타/PNG 스텁도 생성하지 않았다.
- 전체 기존136개+신규7개 검사·실제 Windows105상태/픽셀·시간순 움직임·표시창 성능/자원·사용자 체감은 지휘 검수 범위다.
