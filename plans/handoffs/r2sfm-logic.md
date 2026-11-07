# R2-SFM 앞오른쪽 이동 공격 검수

기준선 `db03c9c`에서 기존 검사 8개를 통과했다.

- 실제 메타로 12단계×8보행 위상 96셀의 소스·발점 매핑과 `.18초` 단일 타격·`.60초` 공격 해제를 확인했다.
- SDL dummy/software의 실제 게임 경로와 고정dt로 정지↔이동 전환, 후진·옆걸음, 벽 앞 정지와 종료 뒤 일반 보행 복귀를 확인했다.
- 실제 `CombatWorld`와 `Locomotion`으로 공격 중 36px 이동, 분할시간별 위상, 벽에 막힌 거리 0과 재출발 시 위상 전진을 확인했다.

기준선 결과는 `output/review/R2-SFM-logic/baseline.json`에 저장했다. 동결 소스로 같은 8개를 통과했고 `final.json`을 기록했다. 96셀 매핑·타격/종료·정지/이동 전환·후진/옆걸음·벽 정지와 재출발·위상 및 거리 검사가 모두 기준선과 일치했다. FR 정지·이동 PNG, 전투 메타, 관련 게임 코드 6개 중 SHA-256 변경은 `r2aw-attack-walk-front-right-20261106.png` 한 개였다. Windows 렌더와 픽셀 검수는 지휘 범위다.

```powershell
.venv/Scripts/python.exe -B output/review/R2-SFM-logic/check.py baseline
.venv/Scripts/python.exe -B output/review/R2-SFM-logic/check.py final
```
