# R2-AP8 판정과 연결 검수 · 실제 1주차

기준선 `9d6e1d3`에서 다음 검사를 통과했다.

- 주인공 8방향 `.18초` 단일 타격·`.60초` 종료와 정지 96셀·이동 768셀의 단계/보행 인덱스 및 발점 매핑을 확인했다. 실제 메타와 기존 판정/그리기 호출 검사를 사용했다.
- 좀비 8방향 각각 `.299초` HP 3, `.30초` HP 2와 타격 자세, `.721초` 회수 자세, `.80초` 공격 해제를 확인했다. `CombatWorld.update`와 실제 메타의 프레임 선택을 대조했다.
- R2-ZT의 25도 방향 잠금과 SDL queue의 보행 복귀 두 자세·포커스 정지를 확인했다.
- 공격 96셀·복귀 128셀에서 선택 프레임의 alpha span 경계/여백을 `zombie_contains`로 대조했다. 복귀 전수 검사는 합성 변위, 실제 이동 연결은 SDL dummy/software와 고정dt·합성 포커스를 사용했다. PNG와 마스크의 픽셀 비교는 지휘 검수 범위다.

검사기와 결과는 ignored `output/review/R2-AP8-logic/`에 있다. 실행 전후의 입력 SHA-256을 대조하며 기준선과 최종 결과를 각각 저장한다.

```powershell
.venv/Scripts/python.exe -B output/review/R2-AP8-logic/check.py baseline
.venv/Scripts/python.exe -B output/review/R2-AP8-logic/check.py final
```

`baseline.json`은 기준선, `final.json`은 UI 동결 후 실제 소스 결과다. 최종 실행은 집중 검사 4개, 좀비 8방향 판정, 공격 96셀·복귀 128셀의 현재 마스크 대조를 모두 통과했다. 기준선과 판정·매핑·픽킹 결과가 일치했다.

두 결과의 입력 SHA-256을 비교해 주인공 7방향의 정지·이동 PNG 14개와 좀비 공격 PNG/JSON 2개, 총 16개 변경을 확인했다.
