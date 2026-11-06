# Dead Route 채팅 운영

기준일: 2026-11-06
현재 기준은 [PRD](../PRD.md), 순서는 [개발 계획](development-roadmap.md)입니다.
실제 지시·보고·수정·중간 커밋·사용자 확인은 [지휘 실행 절차](commander-runbook.md)를 따릅니다.

| 역할 | 담당 |
| --- | --- |
| 지휘 | 사용자 요구·범위·작업 배분·연결 규격·검수·수정 요청·문서·Git |
| 로직 개발 | game/core.py, game/locomotion.py, game/spatial_audio.py, game/requirements.txt, 논리 테스트 |
| UI·에셋 | game/main.py, game/player_visual.py, game/visibility.py, game/assets/, 렌더 검증 |

위 경로는 담당 범위이며 아직 없는 모듈은 해당 기능 작업 때만 만듭니다. 현재 core.py·locomotion.py·main.py·player_visual.py와8방향·방향당8장 보행 및 정지 에셋·검사 코드를 작성했습니다.

## 연결 기준

- world(x,y)는 발 접지점, 왼쪽 아래 원점의 지면 px, 시간은 초·조준각은 rad입니다.
- UI는 지면→화면 배치와 화면 마우스→지면 조준 변환을 담당합니다. 로직은 지면 좌표로 이동·거리·충돌·소음·타격을 판정합니다.
- API·입력·이벤트·발점·이미지 크기·방향·프레임·장비 손은 구현 전에 지휘를 통해 합의합니다.
- R1-A 샘플 뒤 R1-B4방향·R1-C8의8방향 보행을 연결했고, 사용자 명시 요청으로 R2-C8의8방향 전투까지 확장했습니다. 각 묶음은 지휘1차 검수 뒤 사용자2차 확인과 다음 진행 요청을 거쳐 진행합니다.
- 시야와 타격의 지면 벽 데이터를 공유하고 캐릭터 노출·건물 전경 가림은 화면 담당이 별도로 검수합니다.
- 시야 밖 소리는 유지하되 이벤트는 한 번만 소비하고 종료·재시작 때 자원을 정리합니다.

## 작업과 Git

지휘가 목적·담당 파일·입출력·완료 기준을 정하고 담당은 필요한 상대 변경을 지휘에게 전달합니다.
지휘가 실제 결과·실행 증거를 확인하고 수정 요청 후 중간 커밋합니다.
각 작은 작업 묶음마다 지휘 1차 검수·수정 후 사용자 2차 확인을 기다립니다. 사용자 확인과 다음 진행 요청 전에는 다음 묶음에 착수하지 않습니다.
공유 Git 인덱스의 stage·commit·branch·push는 지휘만 실행합니다.
브랜치는 planning/first-presentation, 커밋은 `<type>: <n>주차 <단계 ID> <한글 설명>`으로 작성하며 [주차별 기록](weekly-development-log.md)을 갱신합니다. 푸시는 업로드 요청 때 수행합니다.
새 기능·담당 밖 파일 변경은 합의 없이 진행하지 않습니다.

## 현재 인계

현재 R2-ZA 좀비8방향 공격64자세·실제 타격 적용·지휘 검수 후 사용자2차 확인 대기. 이번 계약의 파일 소유권을 일반 역할표보다 우선함. UI·에셋은 새 r2za-* 팔/설정/제작/검사·PNG/JSON, 로직은 combat.py/combat_visual.py/main.py·준비/타격/회복·피격취소/시간분할·현재소스alpha/R/회귀검사, 지휘는1차시각/코드·Windows/성능·수정요청·Git 담당. R2-Z105상태/기존도구·플레이어·core/locomotion/player_visual 보존. [계약](r2za-zombie-attack-contract.md)·[검수](handoffs/r2za-zombie-attack-review.md)를 따르며 다음 기능은 사용자 확인/요청 뒤 배정.

R1-A 기존 그림체에서 UI-02/03 수정·입력·창 검수를 수행했고 이후 도트풍 캐릭터를 적용·지휘 재검수했습니다. 전체 자동 검사 38개·Windows 렌더 3장을 확인했으며 로직 판정은 유지했습니다.
이전 R1-W3에서 로직은 보행 주기, UI·에셋은 앞오른쪽 중간 자세를 담당. 지휘는 같은 경로의 32px/64px 및 같은 64px에서의 그림 차이를 분리 검수. [W3 인계](handoffs/r1-walk-cadence-review.md) 참조. 이전 실제 성능은 [1주차 기록](handoffs/r1-week1-review.md) 참조.
구형 검증 결과를 새 2.5D의 통과 근거로 보고하지 않습니다.

| 채팅 | 로컬 식별자 |
| --- | --- |
| Dead Route · 지휘 | 01a18a70-01de-7cc2-9862-9de99c6b5a82 |
| Dead Route · 로직 개발 | 01a19ece-e161-78c3-adb0-297eba70e204 |
| Dead Route · UI·에셋 | 01a19ece-e348-7db1-ba4e-4076a3f16a0f |
