# Dead Route 게임 개발 폴더

상태: 2026-11-06 R2-FR12 앞·오른쪽 공격12자세 적용·8방향 전투 연습장
기준은 [PRD](../PRD.md)와 [개발 순서](../plans/development-roadmap.md)입니다.
작은 2.5D 장면의 발 접지·지면 이동·마우스 조준·건물 앞뒤 가림을 연결했습니다.
마우스로 몸의8방향 자세를 선택하고 실제 이동 거리로 방향당8장 보행을 재생합니다. 방향당 정지1장 포함 총72자세. 벽에 막히거나 정지하면 idle이며 뒤로·옆으로 걸어도 조준 방향을 유지합니다.
현재 90px/s로 이동하고 64px마다 양발 한 주기를 재생함. 앞발이 바뀌는 간격은 약 0.356초.
R2-FR12 표시창 실제 루프10초 측정: 약240FPS·프레임 간격p95 4.28ms·50ms초과0회. 합성 SDL 입력/포커스 대체를 사용한 현재 환경의 측정이며 사용자 조작감과 구분.
승인 원화의 idle·머리/상체 픽셀 보존, 양발 교대와1px 눌림 적용. [현재 보행 검수](../plans/handoffs/r1-consistent-walk-review.md), [이전 보행](../plans/handoffs/r1-walk-cadence-review.md), [이전 성능](../plans/handoffs/r1-week1-review.md) 구분.

기존 .venv를 재사용합니다. 처음 설치해야 하는 경우 프로젝트 루트에서:

    py -3.13 -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -r game/requirements.txt

프로젝트 루트에서 실행:

    .\.venv\Scripts\python.exe game/main.py

자동 검사:

    .\.venv\Scripts\python.exe -m unittest discover -s game/tests -v

직접 확인: WASD 이동, 마우스로 좀비 몸을 조준해 좌클릭 8방향 공격. 누른 채 자동 반복하지 않으며 준비→타격→회복0.6초. 좀비5타 처치·제자리0.4초 경직·플레이어HP3, R로 위치/체력/전투 전체 재시작.
Esc로 종료. 앞·오른쪽 공격은12단계×걷기8위상, 나머지7방향은6단계×8위상 유지. 전체 정지54·이동432자세. 공격각 잠금·정지/벽의 정지 공격·재출발/종료의 걸음 박자 유지. [FR12 검수](../plans/handoffs/r2fr-smooth-review.md) 참조. 다른 방향 중간 자세·좀비 상세 모션·감지/소음·손전등·배달은 후속 범위.

사용자 명시 요청으로 R2-FR12까지 연결했으며 이번 실행본의 사용자2차 확인 뒤 다음 작업 범위를 결정함.
이전 시제품·실행 파일은 삭제했습니다. 과거 코드는 Git 커밋 7b46edd에서 필요한 부분만 참고합니다.
리소스는 실제 사용할 때 assets/에 추가하고 출처·방향·프레임·발점 규격을 기록합니다.
현재 유지한 [시점 참고 그림](../presentation/assets/2_5d-reference-20261103.png)은 게임용 방향별 스프라이트가 아닙니다.
