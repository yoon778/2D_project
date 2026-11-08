# R2-ZR 좀비 후면 회수 검수 · 11월 8일 2주차

기준선 `7803fc3`에서 실제 `CombatWorld`와 `CombatVisual`로 후면 8→9→10번째 셀 전환을 통과했다.

- `.299초` 무피해, `.30초` 피해 1회, `.40/.46/.52초`에 8/9/10번째 셀 선택을 확인했다. 실제 메타의 셀 좌표와 발점을 `draw_zombie` 호출로 대조했다.
- 셀마다 80×80개 좌표를 `mouse_target`에 전달했다. 총 19,200개가 현재 메타의 alpha 마스크에 따라 좀비 발점 또는 지면 좌표로 연결됐다. PNG와 마스크의 픽셀 대조는 지휘 검수 범위다.
- `.80초` 정상 해제·idle, 이후 실제 이동 1/4px에서 복귀 두 장, 8px에서 일반 보행과 위상 누적을 확인했다. 실제 에셋을 사용한 SDL queue 회귀 2개도 통과했다.

`output/review/R2-ZR-logic/`의 `baseline.json`과 동결 소스 `final.json`을 대조했다. 타격·8→9→10 전환·재보행 기록이 일치했고 클릭 19,200개와 SDL queue 2개를 다시 통과했다. 입력 해시 차이는 좀비 공격 PNG/JSON 2개였으며 JSON 구조에서 후면 9번째 `opaque_rows`만 달랐다. 9번째 마스크의 불투명 좌표는 1,115개에서 1,177개로 바뀌었다.

```powershell
.venv/Scripts/python.exe -B output/review/R2-ZR-logic/check.py baseline
.venv/Scripts/python.exe -B output/review/R2-ZR-logic/check.py final
```
