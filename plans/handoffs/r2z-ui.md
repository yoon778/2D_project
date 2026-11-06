# R2-Z UI·에셋 인계 — 2026-11-06

기준선 `e85cc07`, 계약 `plans/r2z-zombie-contract.md`. 지휘가 제공한8방향 원화에서 정지8·보행64·피격32·단일corpse1, 총105상태를 제작했다. 지휘 외형/모션/실제 화면 검수 승인 후 PNG·JSON을 동결했으며 이후 게임 리소스 재쓰기는 없다.

## 소유 결과

- `art/zombie/studies/zombie-turnaround-ai-20261106.png`: 지휘 제공 원화, 추가 AI 생성 없음
- `prepare-native.cjs`·`r2z-source.json`: 전체 공통5/28 등방 배율·실제 부츠 발점 평행이동·공통 팔레트 정규화
- `zombie-idle-native-20261106.png`·`palette.json`: native320×160, 80셀8방향, 실제24색·이진alpha
- `r2z-zombie-assets.cjs`·`r2z-rig.json`·`parts/`: 같은 방향의 실제 바지/부츠를 분리한 관절 제작. 손 아래 가려진 바지만 같은 원화 바지 재질로 복원하며 복사 좌표를 기록한다
- `raster.cjs`: native 합성·아틀라스 배치·정확한 alpha 클릭 마스크
- `check-r2z.cjs`: 읽기 전용 검증과 임시 출력 재현
- `game/assets/zombie/r2z-zombie-20261106.png/json`: 640×1120, 8열14행·root(40,72)·기준64·2배nearest·stride64

방향은 각 원화의 독립8뷰를 사용한다. 전신 미러/회전으로 방향을 만들지 않았다. 보행은 기존 거리 기반8위상의 양발 관절을 사용하고 상체/손은 원본을1px bob과 함께 유지한다. 피격은 상체·엉덩이의 짧은 반응이며 native66행 이하의 부츠/발바닥은 모든4단계에서 idle와 동일하다. 마지막 .26~.40초는 같은 방향 idle로 완전히 복귀한다. 사망은 같은 앞오른쪽 원화 부품을 조립한 단일 정지 자세다.

PNG/JSON 배치는 계약과 동일하다. row0 idle, row1..8 walk, row9..12 hit, row13 col0 corpse이며 남은7셀은 RGBA0이다. 모든105frame에 해당 셀 alpha와 정확히 같은 `opaque_rows`를 저장했다. 기존 전투JSON/PNG·플레이어·생산코드·Git 작업은 없다. 새 zombie README는 지휘 담당이며 수정하지 않았다.

## 검증 결과

`node art/zombie/check-r2z.cjs` 통과:

- 105상태·8방향 idle 모두 고유, 각 방향 walk8·hit4 모두 고유
- 전체24색, alpha0/255, 셀 가장자리0, 1~2픽셀 고립0, 분리된 큰 부품0(각 상태8연결 성분1)
- `opaque_rows` 672000픽셀 완전 일치, 모든clip·절대pivot·피격 경계0/.06/.14/.26/.40 일치
- idle8셀 정규화 원본 동일, 마지막 hit8셀 idle와 RGBA 동일, 피격32셀 부츠/발바닥 고정
- 보행 상체/손 원본48512픽셀 일치. 골반 상단3행은 몸/다리 이음을 유지하며, 원본 상체/손을 제외한 그 아래 노출 다리 윤곽5007픽셀의 어두운 윤곽색을 확인했다
- 기준선의 플레이어 원화/설정/부품/PNG·기존 전투JSON/PNG·core/combat/locomotion/player_visual 불변
- 지휘 제공 원화 SHA-256 전후 동일, import 부작용0
- 원화→native→105상태 전체를 메모리/`output/review/R2-Z-art/reproduction/`에 재현해 native/최종 PNG2개 바이트 동일, JSON1개는 파싱한 값 동일 확인. JSON은 Git autocrlf의 CRLF/LF 차이를 허용한다. 보고값은 `reproducedPngs:2`·`reproducedJsonValues:1`로 구분하며 동결 이후 게임 리소스 재쓰기0

정규화에서 Sharp PNG 팔레트 옵션만으로24색 상한이 보장되지 않아 명시적인 공통23색 median-cut 매핑과 윤곽1색으로 교정했다. 방향별 세로 압축·개별 키 맞춤은 없다.

## 실제 크기와 검수 자료

기준 신체64는 고정 메타 기준이다. 실제 alpha bbox 높이는 idle63~64px, 보행62~69px, 피격62~66px이며 관절 투영·보행/반응 자세에 따른 범위다. 모든 걷기 그림을64px로 압축하지 않았다. corpse bbox는65×30px이다. 방향별 상세 크기는 `asset-check.json`에 기록했다.

`output/review/R2-Z-art/`:

- `zombie-idle-eight-4x.png`, `player-zombie-comparison-3x.png`
- `walk-eight-directions-3x.png`, `hit-eight-directions-4x.png`, `corpse-6x.png`
- `material-repairs.json`: 가려진 바지 원본 복사 좌표
- `asset-check.json`: 최종 규격·마스크·윤곽·불변·재현 수치

향후 전체 제작 명령은 `node art/zombie/prepare-native.cjs` 후 `node art/zombie/r2z-zombie-assets.cjs`이며 기존 도구와 같은 Sharp 환경이 필요하다. 이번 동결 이후에는 검증 코드의 메모리/임시 출력 경로만 실행했다.

이 보고서의 자체 수치는 오프라인 에셋 검증이다. 실제 SDL·물리 입력·게임 체감·실시간 성능은 지휘 검수와 구분한다. 담당파일 동결 상태로 사용자2차 확인을 기다린다.
