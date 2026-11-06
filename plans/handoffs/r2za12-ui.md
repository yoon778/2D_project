# R2-ZA12 UI·에셋 인계 — 2026-11-06

기준선 `2e954a6`, 계약 `plans/r2za12-zombie-attack-contract.md`. 좀비 공격을 방향당8→12자세, 전체64→96셀로 확장했다. 지휘 FR12/신규32자세 시각 검수 통과, 추가 그림 수정 없음. 제품 PNG·JSON과 담당파일 동결 상태다.

## 변경

- `art/zombie/r2za-zombie-attack.cjs`: 원래 관절 결과 사이에 고정 뼈 길이·짧은 각도/손 회전으로4중간 자세 추가
- `art/zombie/r2za-check.cjs`: 96셀·기존64키·원래rig/부품·현재 보존 범위 검사
- 기존 `game/assets/zombie/r2za-zombie-attack-20261106.png/json`: 같은 파일명/스키마,640×960·80셀8열12행
- 이 인계문서. 원래 `r2za-rigs.json`·팔 부품·마스크·cleanup·몸/옷감 복원 값은 변경하지 않았다. 중복 없이 모두12고유여서 신규 중간 설정도 필요하지 않았다
- Python·Git 작업 없음. 공유 트리의 Python 검사/로직 보고서는 로직 담당 소유다

시간 경계는0/.04/.08/.12/.16/.23/.30/.40/.46/.52/.64/.72/.80초다. 원래8키는 신규행0/2/4/6/7/9/10/11에서 원래 시작시간과 RGBA를 유지한다. 신규행1/3/5/8만 추가했고 .30 타격·.72 원본idle·.80 종료는 그대로다. 몸통/머리/바지와 고정 하체는 동일하며 전신 회전·미러·스케일 변경·잔상은 사용하지 않는다.

## 검사 결과

`node art/zombie/r2za-check.cjs` 통과:

- 96셀·신규32중간·방향별12고유
- 기존64키 RGBA 완전 일치, 원래 키 시작시간 유지
- 96셀의58행 이하 하체/부츠 RGBA 동일, 마지막8셀 기존 R2-Z idle와 동일
- 실제24색·alpha0/255·가장자리0·1~2픽셀 고립0·큰 분리0(모든 상태8연결 성분1)
- `opaque_rows`614400픽셀 정확, clip·절대pivot(40,72)·기준64·2배nearest·13시간 경계 일치
- 팔 제거+새 팔 coverage 밖 변경0, 고정 base 머리2231픽셀과 기존 바지 복원221픽셀 기준 유지
- 고정 뼈 길이352건·손 tip 앵커176건·분리 부품 팔꿈치/손목8연결 접점352건 통과
- 원래rig 값/팔 마스크/cleanup 동일, 기존 좀비/플레이어 입력·부품·리소스와 보존 생산파일316개 변경 없음. 이번에는 combat.py도 보존한다
- 메모리/ignored 임시 폴더 재현에서 PNG1개 바이트 동일·JSON1개 값 동일(CRLF/LF 허용), import 부작용0·제품 재쓰기0

앞오른쪽12자세 비교부터 먼저 전달한 뒤 나머지7방향을 제작했다. 첫96상태부터 모든 방향이12고유이고 고립/분리0이어서 신규 중간 경로의 추가 국소 교정은 없었다. 제품 동결 신호 후에는 리소스를 재베이크하지 않았다.

## 검수 자료·명령

`output/review/R2-ZA12-art/`:

- `front-right-attack-twelve-4x.png`, `front-right-old-eight-vs-keys-3x.png`
- `attack-eight-directions-3x.png`: 최종96자세, 방향별 시간순12열
- `middle-four-eight-directions-4x.png`: 신규4자세×8방향
- `pose-joints.json`: 실제 관절·손 각도·손 tip 결과
- `first-raster-check.json`, `asset-check.json`, `reproduction/`: 기존키/고유/정확alpha/재현 근거
- `previous/`: 변경 전8자세 PNG/JSON·rig 비교본

제작 명령은 `node art/zombie/r2za-zombie-attack.cjs`, FR 미리보기는 `--facing front_right` 추가다. 기존과 같은 Sharp 환경이 필요하다. 현재 CLI는 기존 팔 부품 PNG를 다시 쓰지 않는다. 검증은 제작 결과를 메모리로 만들고 임시 `reproduction/`에만 저장하며 제품 PNG·JSON을 수정하지 않는다.

자체 오프라인 검사와 지휘 실제 Windows·실공격/취소·성능 결과를 구분한다. 추가 기능/방향 확장 없이 지휘 최종 검수·커밋·사용자2차 확인을 기다린다.
