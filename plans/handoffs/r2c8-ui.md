# R2-C8 UI·에셋 인계 — 2026-11-06

기준선 `e23de0c`. 1차 수정 시안 재검수에서 앞/뒤 나무면·큰 무기 잔상 해소, 7방향 타격·걷기 교대·깊이 양호 확인. 이후 확대 SDL 검수에서 드러난 5방향 고립 잔여를 원인 마스크로 교정했다. 최종 7방향315활성자세의 8연결1~2픽셀 고립 성분은0이다. 현재 그림·담당파일 동결, 실제 SDL 통합·성능·사용자 조작 검수는 지휘 담당이다.

## 변경 범위

- 새 제작 도구 `art/player/r2c8-combat-assets.cjs`, 방향 설정 `art/player/r2c8-rigs.json`, 읽기 전용 검사 `art/player/check-r2c8-combat.cjs`
- `game/assets/combat/r2c8-attack-<direction>-20261106.png` 7개와 `r2c8-attack-walk-<direction>-20261106.png` 7개
- 기존 `r2a-combat-20261106.json`에 `attack_<facing>`·`attack_walk_<facing>` 14블록 추가
- 지휘 추가 허용 범위: 기존 `art/player/r2a-combat-assets.cjs`에 기존 메타 키 보존만 보완
- R1 helper 추가 export·알고리즘 수정, Python 수정, Git 변경 없음. 공유 작업 트리의 Python 변경은 로직 담당 소유다

## 제작·국소 교정

승인한 각 방향의 몸·전체 다리 부품과 기존 `drawLeg/joints`를 사용한다. 전체 몸 회전·미러 없이 오른팔·손·방망이만 관절로 움직인다. 왼쪽의 가려진 오른팔은 같은 왼쪽 원화의 소매·피부 재질을 사용하며 기존 왼손 택배를 유지한다. 무기는 완전한 데이터를 만든 뒤 깊이 순서로 가린다. 좌우 골반 윤곽과 오른쪽 허벅지 밝은 면을 유지한다.

앞/뒤 방망이의 일부 나무색이 피부색과 같아 기존 색 필터에서 누락되어 있었다. 기존 원화와 무기 기하 마스크의 전체 alpha를 사용해 나무면을 복원했다. 기존 무기는 RGBA 색 일치 대신 전체 coverage를 제거하고 승인된 다리 부품으로 복원한다. `bodyRaw`의 남은 무기와 원래 손의 나무색 하이라이트도 같은 범위에서 제거했다. 원화·분리 부품은 변경하지 않았다.

## 확인 결과

`node art/player/check-r2c8-combat.cjs` 통과:

- 14소스·378자세: 정지 7×6, 이동 7×6×8
- 정지 288×192, 이동 768×576, 96셀·피벗(48,80)·기준64·2배·단계 경계/인덱스 일치
- 복귀 63장: 정지7장·이동56장 모두 현재 R1 PNG의 (8,8) 패딩과 RGBA 완전 일치
- 머리 원본 픽셀 비교 113454건 일치, 중간 alpha·팔레트 이탈·셀 가장자리 alpha 모두 0
- `attack`·`attack_walk`·`zombie` 기존 3블록 기준선 동일
- R1 원화/설정/helper/부품/메타/PNG, 기존 FR·좀비 PNG, core/locomotion/player_visual/combat.py 기준선 diff 없음
- 새 제작 도구 require 출력·리소스 변경 0

기존 r2a 전체 제작과 새 r2c8 전체 제작을 각각 실행하여 전투 PNG 17개 바이트 및 메타 17블록 전체 동일 확인. 기존 도구 실행 후에도 새14블록이 보존된다.

## 지휘 확인 경로

- `output/review/R2-C8-art/stationary-seven-directions-2x.png`
- `output/review/R2-C8-art/hit-walk-seven-directions-2x.png`
- `output/review/R2-C8-art/pose-joints.json`
- `output/review/R2-C8-art/asset-check.json`
- `output/review/R2-C8-art/rebuild-check.json`

## 확대 SDL 검수 후 국소 교정

등 정지0의 96셀 좌표 (64,76) 검정점, 앞왼쪽 (37,48)·(36,52) 갈색점과 등 무기 밑 L형 꼬리를 확인했다. 원인은 원래 팔 제거 팔레트에서 빠진 갈색/피부색, 원래 손 마스크 오른쪽 밖 테두리 3픽셀, 기존 방망이 마스크 밖 테두리 1픽셀이다. `removeForeColors`·`hand.removeMask`·`oldBatExtras`는 원래 부품을 제거하는 범위만 보완한다. 새 팔/손/방망이의 재질·길이·관절·합성 순서는 바꾸지 않는다. 단계별 출력 픽셀 삭제나 전체 고립 요소 삭제는 사용하지 않았다.

- 두 방향 각각 5공격단계×(정지1+보행8), 총90자세·378픽셀 변경
- 전후 RGBA 차이 전체가 해당 원화의 원인 마스크 안에 있음. 마스크 밖 변경0, 나머지5방향 PNG10개 바이트 동일
- 전체63복귀셀 RGBA 동일, 35관절 기록 및 제거 전용 설정을 제외한 기하 설정 동일
- 정상적으로 가려진 무기 조각과 원본 골반 윤곽은 보존. 기존3고립점 소멸을 전용 검사에 추가했고 기존 규격/불변 검사도 재통과
- 원본 대조·단계별 변경 수: `output/review/R2-C8-art/cleanup-check.json`
- 수정 확대 그림: `output/review/R2-C8-art/detail-back-corrected.png`, `detail-front-left-corrected.png`

비교 기준 PNG14개·제작도구/설정·관절 기록은 `output/review/R2-C8-art/pre-island-fix/`에 보관했다. 기존7방향 비교 시트는 수정 그림으로 갱신했다.

## 마지막 3방향 잔여·전체 활성 자세 검사

앞 방향의 원래 팔 갈색 `5b3e35/8a5430`와 방망이 테두리(native26,52), 뒤오른쪽 팔 `5b3e35`, 뒤왼쪽 팔 `392b29`도 제거 팔레트에 빠져 있었다. 같은 제거 전용 설정으로 보완했다. 변경 전후 비교에서 이3방향6PNG·126자세·162픽셀만 달라졌고 원인 마스크 밖 변경은0이다. 나머지4방향 PNG8개(앞서 교정한 등/앞왼쪽 포함) 바이트, 전체63복귀셀 RGBA, 기하 설정과35관절 기록은 동일하다.

`node art/player/check-r2c8-combat.cjs`에 최종315활성자세의 8연결1~2픽셀 성분 검사와 보고된8좌표 회귀 검사를 추가했다. 둘 다0잔여로 통과했고 규격·팔레트·원본 보존 검사도 통과했다. 정상 무기 조각을 통째로 삭제하는 처리 없이 원본 부품 제거 마스크만 보완했다.

- `output/review/R2-C8-art/eight-connected-check.json`: 7×5×9=315자세, 1~2픽셀 성분0
- `output/review/R2-C8-art/final-cleanup-check.json`: 마지막3방향의 단계별 차이·원인 마스크·불변 대조
- `output/review/R2-C8-art/pre-final-remnant-fix/`: 마지막3방향 수정 직전 비교 원본
- `output/review/R2-C8-art/asset-check.json`: 최종378자세·315활성자세·8좌표·63복귀 등 통합 에셋 검사

시트와 PNG는 마지막 교정 상태로 고정했다. 추가 미술·기하·프레임 확장은 없다.

위 출력은 로컬 검수 자료다. Windows 실제 SDL·물리 입력·플레이 감각·실시간 성능 통과 증거로 사용하지 않는다. 추가 미술/구조/프레임 확장 없이 지휘 통합 검수 결과를 기다린다.
