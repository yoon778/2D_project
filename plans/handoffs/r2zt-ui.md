# R2-ZT UI·에셋 인계 · 2026-11-07

기준선 `b6a0a0f`, 계약 `plans/r2zt-zombie-transition-contract.md`. 좀비 공격 정상 종료 후 첫 8px의 걷기 복귀에 쓰는 두 자세를 8방향 × 8개 목표 보행에 맞춰 추가했다.

- `game/assets/zombie/r2z-zombie-20261106.png/json`은 640×2400으로 확장했다. 기존 상단 640×1120의 RGBA와 원래 105셀의 프레임 기록을 보존했다.
- 신규 128셀은 0부터 세는 행 `14 + 2 * walk_index + step`에 배치했다. `facings[name].resume[walk_index][step]`의 80×80 clip, 절대 발점(셀 기준 40,72), 실제 alpha 마스크를 기록했다. 원래 2배 표시와 24색 유지.
- 기존 관절·부츠에서 목표 보행까지 1/3, 2/3을 적용했다. 먼 다리, 가까운 다리, 몸통 순서로 합성해 기존 팔·옷감 가림을 유지했다. 보행 1·5의 1px 몸통 이동은 픽셀 격자에서 둘째 장에 반영된다.
- 기존 공격 96셀 PNG·JSON, 원화·리그·부품 보존. 발점은 기존 공통 앵커다. 월드 좌표와 조작감은 실제 게임 검수 범위다.

## 검사

`node art/zombie/r2zt-check.cjs` 통과. 복귀 128셀의 819,200개 alpha와 마스크가 일치했다. 전 셀 이진 alpha, 기존 색만 사용, 테두리 접촉·분리 픽셀 0, 상체 RGB·alpha와 배치 일치. 메모리 재현 PNG 바이트와 JSON 값 일치. 검사 중 제품 파일 재쓰기 0.

64개 연결 모두 각 인접 단계의 RGBA·alpha 변화 픽셀 수가 해당 idle→목표 보행의 직접 변화보다 작았다. 인접 변화는 RGBA 43~927px, alpha 5~154px. 고정 셀에서 계산한 픽셀 변화량이다. 앞오른쪽 전 위상과 8방향 대표 위상의 부츠·다리 윤곽과 팔 가림을 비교 시트에서 확인했다.

## 재현

- 제작 `node art/zombie/r2z-zombie-assets.cjs`. 기존 native 원화와 부품 추출 로직으로 전체 233셀을 제조하며 부품 파일은 다시 쓰지 않는다.
- 앞오른쪽 미리보기 `node art/zombie/r2z-zombie-assets.cjs --preview`. 제품 PNG·JSON 쓰기 없이 비교 시트만 생성한다.
- 기존 Sharp 환경 사용. 이번 작업의 `NODE_PATH`는 `C:/Users/cys04/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules`.
- `output/review/R2-ZT-art/`의 방향별 `*-resume-3x.png`는 행 0~7, 열 idle→1/3→2/3→목표 보행. `representative-eight-directions-3x.png`는 방향별 직접 alpha 변화가 가장 큰 위상, `asset-check.json`은 64개 연결별 검사값.

제품 PNG·JSON 동결. 지휘의 실제 Windows 검수와 사용자 2차 확인 대기.
