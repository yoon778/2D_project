# Dead Route 게임 개발 폴더

상태: 2026-11-07 R2-SW 주인공 앞오른쪽 스윙·명중 표시 비교. 지휘 1차 검수 완료, 사용자 2차 확인 대기
기준은 [PRD](../PRD.md)와 [개발 순서](../plans/development-roadmap.md)입니다.
작은 2.5D 장면의 발 접지·지면 이동·마우스 조준·건물 앞뒤 가림을 연결했습니다.
마우스로 몸의8방향 자세를 선택하고 실제 이동 거리로 방향당8장 보행을 재생합니다. 방향당 정지1장 포함 총72자세. 벽에 막히거나 정지하면 idle이며 뒤로·옆으로 걸어도 조준 방향을 유지합니다.
현재 90px/s로 이동하고 64px마다 양발 한 주기를 재생함. 앞발이 바뀌는 간격은 약 0.356초.
이전 R2-Z 표시창10초 측정은 [걷기·피격 검수](../plans/handoffs/r2z-zombie-review.md)에 보존. 현재 공격본의 실제 검증/성능과 사용자2차 항목은 [R2-ZA 검수](../plans/handoffs/r2za-zombie-attack-review.md)에 기록함. 합성 SDL 입력/포커스 대체와 사용자 조작감은 구분함.
승인 원화의 idle·머리/상체 픽셀 보존, 양발 교대와1px 눌림 적용. [현재 보행 검수](../plans/handoffs/r1-consistent-walk-review.md), [이전 보행](../plans/handoffs/r1-walk-cadence-review.md), [이전 성능](../plans/handoffs/r1-week1-review.md) 구분.

기존 .venv를 재사용합니다. 처음 설치해야 하는 경우 프로젝트 루트에서:

    py -3.13 -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -r game/requirements.txt

프로젝트 루트에서 실행:

    .\.venv\Scripts\python.exe game/main.py

자동 검사:

    .\.venv\Scripts\python.exe -m unittest discover -s game/tests -v

직접 확인: WASD 이동, 마우스로 좀비 몸을 조준해 좌클릭 8방향 공격. 누른 채 자동 반복하지 않으며 준비→타격→회복0.6초. 좀비5타 처치·제자리0.4초 경직·플레이어HP3, R로 위치/체력/전투 전체 재시작.
Esc로 종료. 주인공8방향 모두 공격12단계×걷기8위상, 전체 정지96·이동768자세. 공격0.6초/타격0.18초·공격각 잠금·정지/벽의 정지 공격·재출발/종료의 걸음 박자 유지. [8방향12자세 검수](../plans/handoffs/r2c812-combat-review.md) 참조.

좀비는 같은64px 도트풍·8방향별 정지1/걷기8/피격4·공통corpse1, 총105상태. 실제 거리64px마다 양발 교대, 경직0.4초 동안 발점·보행 위상 고정 후 재개. 마지막 피격은 idle과 동일. 몸 클릭은 현재 자세의alpha를 사용하며 죽으면 클릭 대상에서 제외. [좀비 검수](../plans/handoffs/r2z-zombie-review.md)·[리소스 규격/제작](assets/zombie/README.md) 참조. 감지/소음·손전등·배달은 후속 범위.

R2-ZA는 좀비 공격8방향×8자세를 추가함. 접촉 즉시 피해 대신0.8초 준비/타격/회복·0.30초 피해1회. 시작/타격28px·전방±50도·벽 재검사, 공격 중 제자리/방향 잠금·후퇴로 회피·방망이 피격으로 취소. 공격 중 발/보행 위상 고정 후 같은 박자로 재추격함.
R2-ZA12에서 좀비 8방향 공격을 12자세로 확대함. 당시 전투·성능 검수는 [12자세 검수](../plans/handoffs/r2za12-zombie-attack-review.md) 참조.

R2-ZT는 공격 시작 시 직전 보행 방향을 기준으로 표시 방향을 고정함. 공격이 끝난 뒤 움직이는 첫 8px에 연결 자세 2장을 재생함. [공격 전환 검수](../plans/handoffs/r2zt-zombie-transition-review.md) 참조.

R2-AP8은 공격의 준비·타격·회수에서 상체가 무게 이동을 따라가는 자세를 8방향에 적용함. 주인공 정지·이동과 좀비 공격에 반영. [공격 자세 검수](../plans/handoffs/r2ap8-attack-pose-review.md) 참조.

R2-AP8-R은 일반 보행 7장과 대응하는 마지막 이동 공격 회수 자세에서 분리 윤곽점을 정리함. [회수·보행 검수](../plans/handoffs/r2ap8-r-recovery-review.md) 참조.

R2-SW는 앞오른쪽 정지·이동 공격의 준비에서 타격 직전까지 방망이 각도 변화를 나누고, 명중 시 0.06초 표시를 적용함. [스윙 검수](../plans/handoffs/r2sw-swing-review.md) 참조.
이전 시제품·실행 파일은 삭제했습니다. 과거 코드는 Git 커밋 7b46edd에서 필요한 부분만 참고합니다.
리소스는 실제 사용할 때 assets/에 추가하고 출처·방향·프레임·발점 규격을 기록합니다.
현재 유지한 [시점 참고 그림](../presentation/assets/2_5d-reference-20261103.png)은 게임용 방향별 스프라이트가 아닙니다.
