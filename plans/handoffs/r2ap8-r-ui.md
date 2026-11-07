# R2-AP8-R UI·에셋 인계 · 2026-11-07

기준 `0c7eb9a`, [회수 윤곽 정리 계약](../r2ap8-r-recovery-contract.md). 앞왼쪽·뒤왼쪽 보행 원본의 분리 윤곽을 정리한 뒤 같은 위상의 이동 공격 회수에 반영했다.

| 방향 | 보행 번호 | 80×80 셀 좌상단 기준 0-based 좌표 | 셀당 제거 |
| --- | --- | --- | --- |
| 앞왼쪽 | 4·5 | x32 y67~70, x31 y68~70 | 7px |
| 앞왼쪽 | 6 | x32 y68~71, x31 y69~71 | 7px |
| 뒤왼쪽 | 1·7·8 | x47 y57~60 | 4px |
| 뒤왼쪽 | 2 | x47 y58~61 | 4px |

앞왼쪽은 기존 배트 마스크에 섞인 부츠 외곽 조각, 뒤왼쪽은 추출 몸통의 어두운 잔여 선이다. 원본에서 각각 완전 분리 성분과 일치했다. 보행 7셀의 37픽셀과 회수 7셀의 대응 37픽셀을 `00000000`으로 바꿨다. 이동 회수는 공격 인덱스 11의 96px 셀이며 위 좌표에 (8,8)을 더한다.

- `art/player/consistent-walk.cjs`는 해당 방향·위상에서 완성 셀의 지정 좌표만 지운다. 원화·부품은 보존했다.
- 보행 PNG 두 개를 먼저 동결한 뒤 이동 공격 PNG 두 개를 동결했다. 4개 아틀라스의 승인 좌표 밖 RGBA 동일. 정지·공격 0~10·나머지 방향·좀비·피벗·시간표 보존.
- 보행 PNG 무결성 기록을 맞추기 위해 `r1b-courier-atlas-20261104.json`의 `sources.consistent_back_left.sha256`와 `sources.consistent_front_left.sha256`만 갱신했다. 나머지 메타는 기준과 동일하다.
- `node art/r2ap8-check.cjs` 통과. 보행 2종 메모리 재현, 이동 공격 생성 결과, 두 레이어의 정확한 변경 범위를 검증했다. 조작감과 전환 시점은 실제 게임 검수 범위다.

제작 명령은 `node art/player/consistent-walk.cjs front_left --atlas-only`, `node art/player/consistent-walk.cjs back_left --atlas-only`다. 회수 생성은 기존 `art/player/r2c8-combat-assets.cjs`가 보행 PNG에서 복사한다. 이번 반영은 해당 생성기의 메모리 결과를 대조하고 두 이동 공격 PNG만 썼다. 위 검사 명령은 에셋을 읽기만 한다.

`output/review/R2-AP8-R/`에 보행·회수 `*-before-marked-after.png`와 `*-pixels.json` 저장. 시트는 기존·제거점 표시·수정 순서다.
