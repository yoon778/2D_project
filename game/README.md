# Dead Route 게임 개발 폴더

상태: 2026-11-04 R1-A 한 방향 샘플의 지휘 기술 검수 후 사용자 2차 확인 대기 상태입니다.
기준은 [PRD](../PRD.md)와 [개발 순서](../plans/development-roadmap.md)입니다.
작은 2.5D 장면의 발 접지·지면 이동·마우스 조준·건물 앞뒤 가림을 연결했습니다.
자동 검사 37개, 실제 Windows SDL 사건 재생, 실제 창의 제목·마우스·포커스 복귀·닫기를 확인했습니다. 물리 키보드 조작은 사용자 2차에서 확인해야 합니다.
한 방향 샘플 고정이며 몸 방향 전환·보행 모션은 아직 없습니다.
확인 수단별 결과와 사용자 체크리스트는 [지휘 검수 기록](../plans/handoffs/r1a-review.md)을 따릅니다.

기존 .venv를 재사용합니다. 처음 설치해야 하는 경우 프로젝트 루트에서:

    py -3.13 -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -r game/requirements.txt

프로젝트 루트에서 실행:

    .\.venv\Scripts\python.exe game/main.py

자동 검사:

    .\.venv\Scripts\python.exe -m unittest discover -s game/tests -v

사용자 2차 확인과 다음 진행 요청 전에는 R1-B 구현에 착수하지 않습니다.
이전 시제품·실행 파일은 삭제했습니다. 과거 코드는 Git 커밋 7b46edd에서 필요한 부분만 참고합니다.
리소스는 실제 사용할 때 assets/에 추가하고 출처·방향·프레임·발점 규격을 기록합니다.
현재 유지한 [시점 참고 그림](../presentation/assets/2_5d-reference-20261103.png)은 게임용 방향별 스프라이트가 아닙니다.
