# R2-A 한 방향 공격·좀비 1마리 · 2026-11-06

사용자 승인: 좀비1마리와 한 방향 공격 모션 제작·게임 적용·두 채팅 지시·검수·중간 커밋
기준선 `7da78ea`, 현재 실제 프로젝트1주차에 계획2주차의 최소 전투를 선행함
이 묶음 후 사용자2차 확인에서 정지하며 나머지 공격 방향·R3는 별도 다음 요청 대상

## 범위와 소유권

- 로직: 새 `game/combat.py`, `game/tests/test_combat.py`, 필요시 자기 `plans/handoffs/r2a-logic.md`
- UI·에셋: `game/main.py`, 새 `game/combat_visual.py`, 새 공격/임시 좀비 리소스와 제작 도구, 관련 visual 검사, 자기 `plans/handoffs/r2a-ui.md`
- 지휘: 연결·원화/실행/입력/성능 검수·수정 요청·문서·Git
- 기존 core/locomotion/player_visual와 R1 원화·72자세·메타는 보존. 기존 시각 테스트는 바뀐 시작 조준/제목 등 정당한 기대값만 조정하고 입력·발점 검증을 약화하지 않음
- stage·commit·push는 지휘만 수행. 같은 작업 폴더/브랜치 사용, 담당 밖 변경은 지휘에게 보고

## 로직 연결 API

`from combat import CombatWorld, ATTACK_DURATION, ATTACK_HIT_TIME, STUN_DURATION`

| API | 의미 |
| --- | --- |
| `world = CombatWorld()` | player·walls·zombie 생성, 기존 Player/Wall·이동 함수 재사용 |
| `world.player`, `world.walls`, `world.zombie` | 지면 좌표. player 초기(480,180), 벽(400,330,220,60), zombie 초기(600,100) |
| `world.zombie.hp`, `.stun_remaining`, `.alive` | 최대5, 피격 제자리0.4초, 사망 판정 |
| `world.player_hp`, `.player_invulnerable_remaining` | 최대3, 접촉 피해1·무적1초 |
| `world.attack` | 없으면None, 활성 시 `.elapsed`·`.angle`·`.facing`; 시간은 로직만 진행 |
| `world.start_attack(facing="front_right") -> bool` | 진행 중/회복/사망 시 거절, 시작 때 player 조준각과 표시 방향 고정 |
| `world.update(dt, axis_x=0.0, axis_y=0.0)` | 이동·공격·좀비·피해 갱신. UI에서 move_player를 중복 호출하지 않음 |
| `world.result` | `playing` / `cleared`(연습 좀비 처치) / `defeated`; 후자 둘은 이동/공격 중단 |
| `world.reset()` | 위치·HP·공격·경직·무적·결과 모두 초기화 |

UI는 update 전 `aim_player(world.player, *target)` 호출. 활성 공격 표시에는 고정된 attack.angle 사용, 끝나면 현재 마우스 조준 복귀

## 판정과 입력

- 준비→타격1회→회복: 전체0.6초, 시작 후0.18초에만 판정. 중복 피해·회복 취소·누른 채 자동 연타 금지
- 시작값: 중심간 사거리80 지면px·전방 전체100도. 벽이 타격 선분을 막으면 실패. 범위/각도/벽 밖은 헛스윙
- 좀비는 보이는 플레이어에게 직접 접근하며 기존 벽 충돌 준수. 길찾기·소음·시야 상태기는 R3에서 구현
- 걷기/좀비90px/s, 공격 중 플레이어60px/s. 피격 좀비 위치 밀림 없음. 새 타격/경직/사망을 먼저 처리하고 경직 중 이동·접촉 피해 중단
- 좀비 처치5타, 플레이어 HP0 실패. 결과에서 R로 재시작. 포커스 상실 시 키/대기 클릭 해제·시간 진행 중지, Esc 종료 유지
- 실제 이번 시안의 좌클릭 시작은 현재 앞·오른쪽(front_right) 표시 방향일 때만 허용. 화면에 `앞·오른쪽 조준 후 좌클릭 공격` 안내. 로직은 각도 독립으로 검증하되 아직 없는 공격 그림을 다른 방향으로 회전/반전하지 않음
- 기존8방향 이동/조준은 유지. 좀비가 앞·오른쪽에서 접근하는 배치로 후진하며 거리 조절 검수

## 아트·렌더 연결

- 승인 캐릭터/팔레트·왼손 택배·오른손 방망이 유지. 원화 입력·R1 에셋은 바꾸지 않고 새 공격 아틀라스로 분리
- front_right 한 방향6자세. 준비2→타격→후속→회복→복귀, 경계 `[0,0.09,0.18,0.27,0.37,0.48,0.60]`초. 타격3번 자세와0.18초 판정을 일치시킴
- 셀96×96·3열2행·288×192 PNG, 기존80px 캐릭터를(8,8) 이동한 기준. 피벗(48,80), 신체 기준64·정수2배 nearest, 원본 몸의 비등방 변형 금지. 무기 여백 부족 시 보고하고 절단하지 않음
- 새 공격 메타는 기존 R1 메타와 별도 관리. `CombatVisual`이 공격/임시 좀비를 담당하고 `PlayerVisual`의 보행·입력 API 유지
- `Renderer.draw(player,walls,target,focused=True)` 호출 계약 유지. `renderer.combat`에 월드를 연결하고 필요 시 zombie를 깊이 정렬에 추가
- UI는 elapsed를 복제해 진행하지 않고 world.attack.elapsed로 프레임 선택. 공격에 가려진 동안도 실제 이동 거리의 보행 위상 유지
- 좀비는 우선 단순 도트 임시 외형1개와 경직/사망 구분만 사용. 추가 방향·정교한 좀비 애니메이션 선제 제작 금지
- 이미지/텍스처는 초기화 시 로드, 프레임마다 파일 읽기·생성 금지. 기존 raw SDL polling·포커스 처리·해제 경로 유지

## 완료 기준

1. 의미 있는 전투 판정 검사: 범위/각도/벽·단발 피해·회복 잠금·경직/무적·사망 우선·재시작·dt 경계
2. 기존 이동·발점·자원 정리 회귀와 새 공격 프레임/배율/위상 검사
3. 실제 Windows Renderer에서 준비/타격/회복·5타 처치·제자리 경직·실패/R 재시작·벽 가림 검수
4. 표시창 실제 루프의 프레임 시간 확인, 고정dt 캡처·합성 입력과 사용자 물리 키보드/타격감은 구분
5. 지휘 수정/재검수·중간 커밋 후 사용자2차 확인에서 정지
