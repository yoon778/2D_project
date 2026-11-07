# R2-SFM UI·에셋 인계 · 2026-11-07

기준 `db03c9c`, [이동 스윙 계약](../r2sfm-moving-swing-contract.md). 앞오른쪽 이동 공격 12×8셀을 승인된 R2-SF 정지 상체와 기존 보행 다리로 합성했다. 96px 셀, 발점 (48,80), 타격 .18초와 종료 .60초는 그대로다.

- 공격 1~9의 상체·그립·방망이·택배는 정지 포즈와 같은 레이어를 사용한다. 0·10도 정지 시안과 같은 오른손·방망이 및 원래 상체를 사용한다. 앞뒤 가림 순서를 유지하고 위상별 0/1px bob을 적용했다.
- 기존 8위상의 다리 관절로 다리를 그린 뒤 벨트와 만나는 허벅지 위쪽을 상체 골반에 맞췄다. 무릎 이하, 발 교대, 접지는 보존했다. 인덱스 11의 8셀은 일반 보행 RGBA를 (8,8)에 그대로 복사한다.
- 기준 대비 제품 변경은 `game/assets/combat/r2aw-attack-walk-front-right-20261106.png` 1개. 정지 PNG는 기준 바이트 및 정지 제조 결과와 일치한다. 보행·나머지 방향·좀비·메타·게임 코드는 기준 그대로다.

## 재현·검증

- `node art/player/r2a-combat-assets.cjs`가 새 합성기를 호출해 이동 PNG를 생성한다. 정지는 기존 `node art/player/r2sf-front-right.cjs` 경로다.
- `node art/r2ap8-check.cjs` 통과. 96셀 분리·잘림 0, 이진 alpha, 피벗·clip·정지 재현 일치. 88개 활성 셀의 상체 레이어 86,000픽셀은 bob을 정렬한 정지와 이동 양쪽에서 일치했다. 다리별 무릎 이하 344,960개 RGBA 표본 일치. 최종 8셀은 기존 회수·일반 보행과 동일하다. 에셋 경로 변경 검사에서는 Markdown만 제외한다.
- 승인 시안과 생산 PNG SHA-256 `e9ea4edf3c85a0adbb58748b1f5de6164ac93ce621d5cc83a8da229f10d2449a` 일치.

## 비교 자료

`output/review/R2-SFM/`의 `hit-eight-phases-2x.png`는 .18초 타격의 기존·신규 8위상, `time-sequence-2x.png`와 `before-after.gif`는 60px/s·64px 주기로 계산한 시간순 보행 위상 표본이다. `standing-moving-continuity-2x.png`와 `stand-move-switch.gif`는 정지↔이동의 상체 연속성 비교다. `pixel-check.json`에 위상과 픽셀 검사값을 기록했다. GIF·WebP 모두 .18초 타격과 .60초 길이를 확인했다. 실제 입력과 타격감은 게임 검수 범위다.
