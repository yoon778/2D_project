# Dead Route

게임명: **Dead Route (데드 루트)**

작은 골목에서 좀보이드식 거리 조절과 소음 위험을 겪으며 택배를 배달하는 Python/pico2d 게임입니다.

## 새 시작 기준 — 2026-11-03

- 고정 사선 3/4의 2.5D 도트풍, 왼손 몸 앞 택배·오른손 방망이·가슴등
- 첫 범위는 지도 1개·좀비 1마리·방망이 1종·배달 1건
- [현재 보행과 검수 기록](plans/handoffs/r1-walk-cadence-review.md): 대각선과 상하좌우 총8방향·72자세. 이동속도90px/s·보행 한 주기64px 유지. 64px 기준 도트풍·양발 교대·긴 방망이·정지 자세를 정수2배 표시함.
- 이전 그림체 검수 이력과 도트풍 수정본·실제 키보드 미확인 항목을 구분한 [지휘 검수 기록](plans/handoffs/r1a-review.md)을 따릅니다.

| 위치 | 용도 |
| --- | --- |
| [PRD.md](PRD.md) | 현재 게임의 단일 기획 기준 |
| [개발 순서](plans/development-roadmap.md) | 단계별 작업·완료 기준 |
| [주차별 개발 기록](plans/weekly-development-log.md) | 기존 주차별 목표·실제 수행·검수·커밋 |
| [채팅 협업](plans/team-workflow.md) | 지휘·로직·UI/에셋 담당과 연결 |
| [지휘 실행 절차](plans/commander-runbook.md) | 작업 지시·1차 검수·수정·중간 커밋·사용자 2차 확인 |
| [game/](game/README.md) | 새 구현을 시작할 개발 폴더 |
| [presentation/](presentation/README.md) | 발표용 6장·기획서 14장·90초 대본 |

2D_project.code-workspace로 작업 환경을 엽니다. 개발용 .venv와 로컬 수업 가이드는 유지합니다.
미사용 이전 시제품·PPT·에셋·임시 출력은 삭제했습니다. 이전 코드가 필요하면 Git 커밋 7b46edd에서 참고할 수 있습니다.
브랜치는 planning/first-presentation, 저장소는 <https://github.com/yoon778/2D_project>입니다.
검증한 작업마다 `feat: 1주차 R1-A 도트풍 캐릭터 적용`처럼 실제 작업 주차·단계·한글 설명으로 커밋하며, 푸시는 업로드 요청 때 진행합니다.
