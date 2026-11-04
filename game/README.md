# Dead Route 게임 개발 폴더

상태: 2026-11-04 R1-A 한 방향 샘플 작성, 사용자 컴퓨터 사용 요청으로 지휘 검수 중단 상태입니다.
기준은 [PRD](../PRD.md)와 [개발 순서](../plans/development-roadmap.md)입니다.
작은 2.5D 장면의 발 접지·WASD 이동·마우스 조준·건물 앞뒤 가림을 검수 중입니다.
자동 검사 27개는 통과했지만 실제 입력·포커스 복귀·종료와 수정된 창 제목의 지휘 확인이 남아 있습니다.
한 방향 샘플 고정이며 몸 방향 전환·보행 모션은 아직 없습니다.
현재 중단 지점과 재개 순서는 [지휘 검수 기록](../plans/handoffs/r1a-review.md)을 따릅니다.

기존 .venv를 재사용합니다. 처음 설치해야 하는 경우 프로젝트 루트에서:

    py -3.13 -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -r game/requirements.txt

재개 후 프로젝트 루트에서 실행:

    .\.venv\Scripts\python.exe game/main.py

자동 검사:

    .\.venv\Scripts\python.exe -m unittest discover -s game/tests -v

사용자 재개 요청 전에는 검수 창을 자동 실행하지 않습니다.
이전 시제품·실행 파일은 삭제했습니다. 과거 코드는 Git 커밋 7b46edd에서 필요한 부분만 참고합니다.
리소스는 실제 사용할 때 assets/에 추가하고 출처·방향·프레임·발점 규격을 기록합니다.
현재 유지한 [시점 참고 그림](../presentation/assets/2_5d-reference-20261103.png)은 게임용 방향별 스프라이트가 아닙니다.
