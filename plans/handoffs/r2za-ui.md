# R2-ZA UI·에셋 인계 — 2026-11-06

기준선 `450f3a1`, 계약 `plans/r2za-zombie-attack-contract.md`. 승인된 앞오른쪽8자세를 기준으로8방향×8공격64셀을 제작했다. 기존 팔 잔여·허리 복원부와 뒤오른쪽/앞왼쪽 소매 외곽을 국소 교정했고 현재 PNG·JSON·담당파일 동결 상태다.

## 변경 범위

- 새 `art/zombie/r2za-rigs.json`, `r2za-zombie-attack.cjs`, `r2za-check.cjs`, `r2za-parts/`
- 새 `game/assets/zombie/r2za-zombie-attack-20261106.png/json`
- 이 인계문서. 기존 R2-Z 원화·정규화·rig·64부품PNG·105상태/제작스크립트, 플레이어 전체·기존 전투 리소스 변경 없음
- Python·Git 작업 없음. 공유 트리의 combat/visual/main/테스트 변경은 로직 담당이다

PNG640×640, 80셀8열8행이며 열은 front/FR/right/BR/back/BL/left/FL, 행은8공격단계다. 피벗(40,72)·기준64·2배nearest·24색·이진alpha를 유지한다. 시간은0/.08/.16/.30/.40/.52/.64/.72/.80초, 마지막 .72~.80은 기존 같은 방향 idle와 RGBA 완전 동일하다. 모든 frame에 정확한 `opaque_rows`를 저장했다.

## 제작·국소 교정

동일 방향 원화의 상완/전완/손을 분리하고 고정 길이2관절로 준비→뻗기/접촉→회수한다. 손의 원래 tip을 손목/손 회전과 연결한다. 측면/뒤대각선의 원래 가려진 팔은 같은 방향의 보이는 팔 재질을 사용하며, 원화 미러·전신 회전·체형 배율 변경은 없다. 앞면은 양팔을 몸 앞에, 뒷면은 몸 뒤에 합성하고 다른 방향은 far→몸→near 순서를 사용한다.

기존 팔 제거는 피부색만 골라 지우지 않고 소매/손가락의 전체 원화 coverage를 사용한다. 새 팔에 바지 무늬가 복사되지 않도록 전완/손 재질은 실제 피부와 외곽으로 제한했다. 드러난 허리/바지는 같은 방향 원화의 인접 바지 패치에서 중간톤353139/2b282b/312f3a만 복사한다. 151316/201d21의 진한 가로띠 복사는 제외하고 실제 alpha 외곽1px만 어둡게 복구한다.

뒤오른쪽(48,38)·앞왼쪽(53,41)은 보고된 상태에서 기존 base/source 소매 잔여임을 확인해 sourceCleanup에만 포함했다. 전역 작은 성분 삭제는 없다. 앞오른쪽 최종 승인 후 해당뷰는 유지했고, 최초 전체본 대비 나머지6방향48셀의 RGBA 동일을 확인했다. 최종 교정 뒤에는 제품 리소스를 다시 쓰지 않았다.

## 검사

`node art/zombie/r2za-check.cjs` 통과:

- 64셀·각 방향8고유, 실제24색·alpha0/255·가장자리0
- 모든 상태8연결 성분1, 1~2픽셀 고립0·큰 분리0
- `opaque_rows`409600픽셀 정확, clip/절대pivot/8시간 경계 일치
- 64셀 모두 원래58행 이하 하체/부츠 RGBA 동일, 마지막8셀 기존 R2-Z idle와 완전 일치
- 원래 팔 제거+새 팔 coverage 밖 변경0, 고정 base의 원본 머리2231픽셀 일치
- 새로 복원한 바지221픽셀 중간톤/실제 외곽 조건 충족
- 고정 뼈 길이224건·손 tip 앵커112건·분리 부품 팔꿈치/손목8연결 접점224건 통과
- 기준선의 기존 좀비/플레이어 입력·리소스·보존 생산파일251개 변경 없음
- 현재 제작기로 메모리/임시 폴더 재현: PNG1개 바이트 동일·JSON1개 값 동일(CRLF/LF 허용), import 부작용0·제품 재쓰기0

## 출력·재현

`output/review/R2-ZA-art/`:

- `front-right-attack-eight-4x.png`, `front-right-compare-3x.png`: 승인된 첫 방향 비교
- `attack-eight-directions-3x.png`: 최종64상태 시트
- `pose-joints.json`: 실제 관절/손 tip·각도 기록
- `final-raster-check.json`, `asset-check.json`: 최종 성분/보존/재현 근거
- `reproduction/`: 제품을 수정하지 않는 PNG/JSON 재현 결과

향후 제작 명령은 `node art/zombie/r2za-zombie-attack.cjs`, FR 미리보기는 같은 명령에 `--facing front_right`를 붙인다. 기존과 같은 Sharp 환경이 필요하다. 검사는 생성 함수를 메모리로 호출하고 `reproduction/`에만 출력하므로 동결 제품을 변경하지 않는다.

지휘 실제Windows·실공격/회피/취소·성능 결과와 자체 오프라인 검사를 구분한다. 담당파일 동결 상태로 지휘 최종 검수·커밋·사용자2차 확인을 기다린다.
