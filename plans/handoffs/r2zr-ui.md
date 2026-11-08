# R2-ZR UI·에셋 인계 · 2026-11-08 2주차

기준 `7803fc3`. 좀비 후면 공격 9번째(.46초) 오른팔 회수만 조정했다. `art/zombie/r2za-rigs.json`의 기존 중간 자세 설정 `back.middle[8].right.fraction`에 `0.08`을 넣었다. 생산 조립 코드와 파츠는 그대로다.

| 비교 | 기준 | 수정 |
| --- | --- | --- |
| 8→9 손목 이동 | 20.73px | 6.56px |
| 9→10 손목 이동 | 9.49px | 4.87px |
| 8→9→10 오른팔 기여 픽셀 | 137→36→61 | 137→98→61 |

손목 이동은 상체 이동을 포함한 80px 셀 좌표로 계산했다. 오른팔 기여 픽셀은 오른팔을 제외한 합성과 전체 RGBA를 비교한 값이다.

- 제품은 `game/assets/zombie/r2za-zombie-attack-20261106.png/json`만 갱신했다. 9번째 셀의 국소 (49,24)~(59,41)에 RGBA 109픽셀이 바뀌었다. alpha 추가 76, 제거 14, RGB만 변경 19.
- 나머지 95셀, 왼팔 레이어, 58행 이하 발, idle, 시간·clip·피벗은 기준과 일치한다. 메타 변경은 `facings.back[8].opaque_rows` 한 곳이다.
- 기존 제조 경로 `node art/zombie/r2za-zombie-attack.cjs`에서 재현 가능하다. 이번 반영은 기존 `makeAtlas`로 두 제품만 썼다.
- 읽기 전용 `node art/r2ap8-check.cjs`와 `node output/review/R2-ZR/check.cjs` 통과. 마스크·연결성·범위·재현과 왼팔 보존 확인.

비교는 `output/review/R2-ZR/back-8-9-10-before-after-4x.png`의 위 기존·아래 수정, 수치는 `pixel-check.json`. 제품 동결. 실제 게임 검수는 지휘 담당.
