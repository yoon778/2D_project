# R2-Z / R2-ZA12 좀비 리소스 · 2026-11-07

`r2z-zombie-20261106.png`와 같은 이름의 JSON을 함께 사용함
공격은 별도 `r2za-zombie-attack-20261106.png`/JSON으로 추가하며 기존105상태를 보존함

- 주인공과 같은 고정 사선3/4·64px 도트풍, 정지 신체63~64px·80셀·발점(40,72)·정수2배 nearest
- 방향 순서: front/front_right/right/back_right/back/back_left/left/front_left
- 아틀라스640×1120: row0 정지8, row1~8 보행64, row9~12 피격32, row13col0 공통corpse1. 나머지7셀 투명
- 총105상태, 전역24색·alpha0/255·셀 가장자리 잘림0. 모든 셀에 실제alpha와 같은 `opaque_rows`
- 보행은 실제 이동 거리64px/주기. 피격 경계0/.06/.14/.26/.40초, 마지막 자세는 같은 방향 정지와 RGBA 동일
- 기존 `game/assets/combat/`의 좀비 소스를 시작 시 메모리에서 대체. 기존 파일 수정과 추가 텍스처 로드 없음
- R2-ZA12 공격은640×960·열8방향/행12단계·96상태, 기존과 같은80셀/발점/배율/팔레트.0/.04/.08/.12/.16/.23/.30/.40/.46/.52/.64/.72/.80초 경계·발바닥 고정·마지막idle 동일. 이전64키는 새행0/2/4/6/7/9/10/11에 RGBA 보존
- 같은 뷰의 실제 팔 부품/관절·국소 옷감 복원·팔 깊이 가림으로 제작. 새 공격1텍스처만 추가해 전체 초기 이미지47개, 매프레임/R 재로드 없음

원화: built-in imagegen으로 생성한 [8방향 입력](../../../art/zombie/studies/zombie-turnaround-ai-20261106.png), [프롬프트·입력 역할](../../../art/zombie/studies/imagegen-prompt.md)
원화는1774×887, 공통등방배율5/28·실제부츠 발점 평행이동으로 native화. 방향별 키 늘이기/압축 없음
같은 방향 원화의 바지/부츠를 분리해 양발관절을 연결하고 가려진 재질을 복원함. 플레이어는 스타일/카메라 기준이며 좀비에 플레이어 장비를 재사용하지 않음

제작 설정/스크립트는 `art/zombie/`, 런타임은 이 폴더의PNG/JSON만 필요함. 제작 의존성Node.js+sharp, 실행 의존성은 `game/requirements.txt`

```powershell
node art/zombie/r2za-zombie-attack.cjs
node art/zombie/r2za-check.cjs
```

제작 스크립트는 새 좀비 리소스만 출력하며 기존 플레이어·전투 리소스는 수정하지 않음
checker는 제품 리소스를 읽기 전용으로 검사하고 재현 결과는 ignored 검수 폴더에만 저장함
기존 `prepare-native.cjs`/`r2z-zombie-assets.cjs`는 이전105상태 제작용으로 보존. `check-r2z.cjs`의 전투코드 동결 검사는 당시baseline 전용이며 현재는 새 `r2za-check.cjs`와 Python 검사를 사용함
[12자세 인계](../../../plans/handoffs/r2za12-ui.md)·[현재 검수/2차 확인](../../../plans/handoffs/r2za12-zombie-attack-review.md), 이전 [걷기/피격](../../../plans/handoffs/r2z-zombie-review.md) 참조
