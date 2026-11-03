# 이전 자료 보관

현재 게임명은 Dead Route입니다. 보관본의 제목·파일명은 제작 당시 명칭을 유지합니다.

[2026-11-03-before-restart/](2026-11-03-before-restart/)는 커밋 7b46edd502cf2cd39c66790573dde24d499266b7의 추적 파일 39개를 원본 바이트로 보관한 폴더입니다.
game/·plans/·presentation/은 이동했고 루트 문서·작업 환경 파일은 당시 내용을 복사했습니다.
[SNAPSHOT.json](2026-11-03-before-restart/SNAPSHOT.json)에 경로·크기·SHA256을 기록했습니다.
Git의 줄바꿈 변환으로 원본 해시가 바뀌지 않도록 보관본에는 .gitattributes의 -text 규칙을 적용합니다.

보관본은 수정하지 않습니다. 현재 작업은 루트 PRD.md·plans/·game/에서 진행합니다.
가상환경·PDF·비공개 빌드 자료는 원래 위치에 보존합니다. 원래 game/ 안의 무시된 캐시는 폴더와 함께 이동했으며 스냅샷 목록·Git 제출에서 제외합니다.

## 이전 수직 탑뷰 시제품 실행

프로젝트 .venv가 준비돼 있다면 이 폴더의 이전_시제품_실행.bat를 더블클릭합니다.
보관본 안의 예전 game/실행.bat는 당시 구조를 보존한 파일이므로 공용 환경을 사용하는 바깥 실행 파일을 사용합니다.
프로젝트 루트에서 직접 실행하려면:

    .\.venv\Scripts\python.exe archive/2026-11-03-before-restart/game/main.py

논리 테스트는 보관본 루트를 작업 디렉터리로 사용합니다:

    Push-Location archive/2026-11-03-before-restart
    try { & ..\..\.venv\Scripts\python.exe -m unittest discover -s game/tests } finally { Pop-Location }

이 결과는 이전 시제품에 해당하며 새 2.5D 구현의 검증 근거가 아닙니다.
