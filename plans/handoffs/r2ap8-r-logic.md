# R2-AP8-R 회수에서 보행으로 이어지는 구간 검수

기준선 `0c7eb9a`에서 뒤왼쪽·앞왼쪽 각 8위상, 총 16개 사례와 그리기 호출 128개를 통과했다.

- 위상 중앙을 기준으로 실제 `CombatWorld.update`의 변위를 `PlayerVisual.update`와 `Locomotion`에 전달했다. `.599초` 회수 셀과 `.600초` 공격 해제 직후의 보행 셀이 같은 위상을 선택했다.
- 마지막 공격 1ms에는 0.06px, 다음 보행 1ms에는 0.09px 이동했다. 공격 중 정지는 정지 회수 셀, 종료 뒤 정지는 idle을 선택했다. 두 경우의 위상 유지와 재출발 후 다음 위상 전진을 확인했다.
- 실제 메타로 `CombatVisual.draw_attack`과 `PlayerVisual.draw`를 실행해 셀 선택·2배 배율·발점 화면 좌표를 기록했다. 회수 96셀의 로컬 피벗은 `(48,80)`, 보행 80셀은 `(40,72)`이며 두 호출 모두 현재 월드 발점에 맞았다. Windows 렌더 및 픽셀 비교는 지휘 검수 범위다.

기준선은 `output/review/R2-AP8-R-logic/baseline.json`에 저장했다. 두 SHA-256 필드를 반영한 동결 소스로 최종 실행해 같은 위치에 `final.json`을 기록했다. 16개 사례와 그리기 호출 128개가 통과했고 기준선과 위치·위상·프레임 기록이 일치했다. 변경 입력은 뒤왼쪽·앞왼쪽의 보행 PNG 2개와 이동 공격 PNG 2개, 보행 소스 SHA-256 두 필드를 갱신한 아틀라스 JSON 1개로 총 5개다.

```powershell
.venv/Scripts/python.exe -B output/review/R2-AP8-R-logic/check.py baseline
.venv/Scripts/python.exe -B output/review/R2-AP8-R-logic/check.py final
```
