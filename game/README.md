# Dead Route 게임 개발 폴더

상태: 2026-11-03 재시작 준비, 새 실행 코드는 미착수입니다.
기준은 [PRD](../PRD.md)와 [개발 순서](../plans/development-roadmap.md)입니다.
첫 구현은 작은 2.5D 장면의 발 접지·WASD 이동·마우스 조준·건물 앞뒤 가림부터 시작합니다.
main.py 등은 구현 단계에서 만들며 빈 모듈·가짜 시작 화면을 미리 만들지 않습니다.

기존 .venv를 재사용합니다. 처음 설치해야 하는 경우 프로젝트 루트에서:

    py -3.13 -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -r game/requirements.txt

새 실행 파일과 테스트 명령은 첫 구현 검증 후 기록합니다.
이전 시제품·실행 파일은 삭제했습니다. 과거 코드는 Git 커밋 7b46edd에서 필요한 부분만 참고합니다.
리소스는 실제 사용할 때 assets/에 추가하고 출처·방향·프레임·발점 규격을 기록합니다.
현재 유지한 [시점 참고 그림](../presentation/assets/2_5d-reference-20261103.png)은 게임용 방향별 스프라이트가 아닙니다.
