# Dead Route 게임 개발 폴더

상태: 2026-11-05 R1-W3 보행 박자·앞오른쪽 발 연결 보완
기준은 [PRD](../PRD.md)와 [개발 순서](../plans/development-roadmap.md)입니다.
작은 2.5D 장면의 발 접지·지면 이동·마우스 조준·건물 앞뒤 가림을 연결했습니다.
마우스로 몸의 네 방향 자세를 선택하고 실제 이동 거리로 방향당8장 보행을 재생합니다. 벽에 막히거나 정지하면 idle이며 뒤로·옆으로 걸어도 조준 방향을 유지합니다.
현재 90px/s로 이동하고 64px마다 양발 한 주기를 재생함. 앞발이 바뀌는 간격은 약 0.356초.
이전 baseline의 실제 표시창30초 측정은 약240FPS·프레임 간격p95 4.44ms·50ms초과0회. 현재 모션의 FPS 측정값이 아님.
현재 [보행 비교·검수 기록](../plans/handoffs/r1-walk-cadence-review.md), 이전 [1주차 성능 기록](../plans/handoffs/r1-week1-review.md).

기존 .venv를 재사용합니다. 처음 설치해야 하는 경우 프로젝트 루트에서:

    py -3.13 -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -r game/requirements.txt

프로젝트 루트에서 실행:

    .\.venv\Scripts\python.exe game/main.py

자동 검사:

    .\.venv\Scripts\python.exe -m unittest discover -s game/tests -v

직접 확인: 마우스 사방 조준·WASD 걷기/후진/옆걸음·발 모양·벽 앞 보행 정지·창 전환 뒤 입력 해제
Esc로 종료합니다. 전투·좀비·손전등·배달은 다음 단계입니다.

1주차 지휘 검수 뒤 사용자2차 확인과 다음 진행 요청 전에는 R2를 시작하지 않습니다.
이전 시제품·실행 파일은 삭제했습니다. 과거 코드는 Git 커밋 7b46edd에서 필요한 부분만 참고합니다.
리소스는 실제 사용할 때 assets/에 추가하고 출처·방향·프레임·발점 규격을 기록합니다.
현재 유지한 [시점 참고 그림](../presentation/assets/2_5d-reference-20261103.png)은 게임용 방향별 스프라이트가 아닙니다.
