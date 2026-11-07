# R2-SF 앞오른쪽 정지 공격 검수

기준선 `57f13de`에서 정지 공격 12셀, 명중 표시 3사례, 실제 에셋을 사용한 SDL queue 2개 검사를 통과했다.

- 12개 구간 시작과 종료 직전의 셀을 선택했다. 타격 `.18초`는 5번째 셀, 회수 `.54초`는 12번째 셀, `.60초`는 공격 표시 해제다. 실제 메타와 `draw_attack` 호출로 `(48,80)` 로컬 피벗·2배 배율·발점 정렬을 확인했다.
- `CombatWorld.update`로 명중·헛스윙·벽 차단을 만들고 실제 `Renderer.draw`의 선 호출을 기록했다. 명중 사례에서 `.18초`와 `.239초`에 표시 3선, `.179초`·`.24초`·`.54초`·`.60초`에 표시 0선을 확인했다. 헛스윙과 벽 차단은 모두 0선이었다.
- SDL dummy/software와 고정dt로 정지↔이동 공격 전환, 위상 유지, 종료 뒤 일반 보행 복귀를 확인했다. 실제 Windows 화면과 픽셀 비교는 지휘 검수 범위다.

`output/review/R2-SF-logic/`에 검사기와 기준선 `baseline.json`, 동결 소스의 `final.json`을 저장했다. 최종 실행에서 정지 12셀·명중 표시 3사례·SDL queue 2개를 통과했다. 셀 선택·발점·명중 표시 기록이 기준선과 일치했고 정지↔이동 전환을 재확인했다. 검사 대상인 FR 정지/이동 PNG, 전투 메타와 관련 게임 코드 중 SHA-256 변경은 `r2a-attack-front-right-20261106.png` 1개였다.

```powershell
.venv/Scripts/python.exe -B output/review/R2-SF-logic/check.py baseline
.venv/Scripts/python.exe -B output/review/R2-SF-logic/check.py final
```
