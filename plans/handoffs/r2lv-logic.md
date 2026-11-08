# R2-LV 오른쪽 보행과 좀비 후면 공격 검수 · 2주차

기준선 `26ba4bd`에서 SDL queue 4사례, 142프레임을 통과했다. 실제 `Image.clip_draw` 호출을 기록하면서 원래 그리기를 실행했다.

- 오른쪽 조준 시 idle과 보행 8위상 모두 `consistent_right`를 사용했다. 발점 `(40,72)`·2배 배율·실제 이동 거리/64 위상을 대조했다. 오른쪽 조준에서 D는 +1.5px, A는 -1.5px 이동하면서 같은 오른쪽 아틀라스를 사용했다. 왼쪽 조준에서 D를 누른 경우 +1.5px 이동하면서 `consistent_left`를 사용했다. 재현 조건은 마우스로 오른쪽을 조준한 상태의 보행이다.
- 오른쪽 이동 공격에서 `.583초` 마지막 회수와 `.600초` 일반 보행이 모두 5번째 위상을 선택했다. `attack_walk_right`에서 `consistent_right`로 전환될 때 발점 정렬과 위상이 이어졌다. `.60초`까지 36px, 이후 한 프레임에 1.5px 이동했다.
- 좀비 후면 공격 12셀의 실제 그리기와 `mouse_target`의 76,800개 클릭 좌표를 대조했다. `.30초`에 피해 1회, `.80초`에 공격 해제, 이후 복귀 두 자세와 일반 보행을 확인했다.

검사는 SDL dummy/software와 고정dt를 사용했다. PNG와 마스크의 픽셀 대조 및 Windows 화면은 지휘 검수 범위다.

`output/review/R2-LV-logic/`의 `baseline.json`과 동결 소스 `final.json`을 대조했다. 최종 142프레임과 클릭 좌표 76,800개를 통과했고 위치·위상·소스 선택·판정 기록이 일치했다. 입력 해시 차이는 오른쪽 보행 PNG, 오른쪽 이동 공격 PNG, 주인공 아틀라스 JSON, 좀비 공격 PNG의 총 4개였다. 주인공 JSON의 `consistent_right.sha256`을 이전 값으로 되돌린 바이트의 해시가 기준선과 일치했다. 좀비 공격 JSON 해시도 일치했다.

```powershell
.venv/Scripts/python.exe -B output/review/R2-LV-logic/check.py baseline
.venv/Scripts/python.exe -B output/review/R2-LV-logic/check.py final
```
