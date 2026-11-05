# R1-C8-WALK 공통 원화 보행 · 2026-11-05

상태: 게임 적용·지휘1차 검수 완료, 사용자2차 확인 대기
사용자가 승인한8방향 원화로 전체 보행 제작·게임 적용·두 채팅 지시·중간 커밋을 요청함
기준선 `b665762`, 승인 원화는 `art/player/style-studies/eight-direction-consistency/turnaround-idle-64-v3.png`

## 후속 윤곽 보완 · R1-C8-OUTLINE

사용자 걷는 다리 윤곽 소실 제보. 분리된 부위 단면에 윤곽이 없고 near 다리의 바지색이 far 다리 선을 덮는 원인 재현

- 각 다리의 부츠·종아리·허벅지를 먼저 조립/회전한 뒤 hip+3px 아래 노출 경계만 기존alpha 안쪽 최암색1px로 복원. 기존 dark색은 유지하고 far→near→장비/몸 깊이 순서 보존
- 실제PNG 노출 경계 검사501→0. RGB만707픽셀 변경, 전8방향 alpha/idle/상체 차이0·폭/관절/프레임clip/pivot 동일. 기존21소스·원화·부품·리그·엔진 보존
- 관련 아틀라스4개·Windows8방향 각2초/60프레임/180px·정수2배·벽/위상/종료 검사 통과. 전체80 중복 실행 없이 영향 검사에 집중
- 수정본 표시창 재실행과 응답 확인. 실제 키보드·보행 체감은 사용자2차 확인 대기, 이번 검수는 실시간 성능 측정이 아님

수정 커밋 `74b6c50`. 재발검사 `node art/player/check-walk-outline.cjs`; 리소스만 다시 만들 때 `node art/player/consistent-walk.cjs --atlas-only`
증거는 `output/review/R1-C8-OUTLINE/`의 `outline-baseline.json`·`outline-after.json`·`shape-preservation.json`·`runtime/`. 비교 `left-before-after.png`

## 소유권

| 담당 | 범위 |
| --- | --- |
| UI·에셋 채팅 | 새 `art/player/consistent-*` 제작 도구/부품과 `game/assets/player/r1-consistent-방향-20261105.png` 8개 |
| 로직 채팅 | 아틀라스 메타·관련 검사·`output/review/R1-C8-WALK/`의 Windows 검수 |
| 지휘 | 원화/보행 검토·수정 요청·문서·Git·최종 실행 |

## 연결·검수 기준

- 승인 원화의 방향별 idle 픽셀을 그대로 사용. 머리·모자·의상·장비·골반을 다른 인물처럼 다시 그리지 않음
- 새8방향별 보행8장+idle1장=총72자세. 80px 셀·320×240 PNG·기준높이64·발점(40,72)·정수2배/nearest·공통24색·알파0/255
- 원화/방향별 비등방 확대·축소 금지. 같은 체형에서 부위를 분리해 보행을 만들고 가려진 부위 복원은 필요한 부분만 검토
- 보행 중 투영된 hip→knee→ankle 구간에 다리 텍스처를 장축fit하는 오프라인 스키닝은 허용. 다리 폭은 유지하고 머리·상체·장비는1:1픽셀을 보존. 전체 몸이나 방향별 키를 맞추는 변형과 구분
- 이동90px/s·보행 한 주기64px·기존 입력/조준/충돌 유지. 1번 오른발·5번 왼발 지지, 낮은 발 들림·상체 눌림 최대1native px부터 비교
- 정지 몸높이는64±1px. 보행 중 발이 지면 앞뒤로 뻗어 전체alpha 높이가 달라지는 것은 몸비율 변화와 구분. 머리/골반/장비/지지발을 별도 확인
- 앞오른쪽 시안 지휘1차 검수 후 나머지7방향 확장. 사용자 요청으로 이번8방향 전체 진행은 승인됨
- 8→1 반복·정지/재출발·조준 방향 전환·양발 교대·장비 손/그립·깊이 가림·셀 잘림·잔여선 확인
- 새 메타 소스 추가와 active frames 교체만 허용. 이전 원화/PNG/소스 기록·legacy alias 및 core/main/locomotion/player_visual 유지
- 자동검사와 숨김 Windows 렌더, 실제 키보드/주관적 무게감을 구분. 완료 뒤 사용자2차 확인에서 정지하며 R2 착수 금지

## 결과

- 승인 원화8idle과 RGBA 차이0. 64개walk의 상체는0/1px bob을 제외하고 원화 픽셀 유지. 방향별8개 자세 고유·팔레트24색 이내·알파0/255·셀 경계 접촉0
- FR 무기를 다리 위·몸 아래로 배치. 오른쪽은 무기에 가려졌던 바지 재질/발목을 같은뷰 native픽셀로 복원해 실처럼 가늘어지던 문제 교정. 왼쪽 숨은 다리는 같은뷰 재질 복제·깊이 가림 적용
- 관련4개·전체80개 검사 통과, 최종 상태 기록 후 관련4개 재확인. 기존21소스와 기존PNG/승인master·legacy alias·런타임4파일 보존
- Windows 숨김 실제 Renderer/core에서 방향별2초·60프레임·180px, 정수2배/nearest·벽 앞idle·조준 전환 시 위상 유지·반복경계2회·SDL 종료0 검수
- 지휘가 전8방향9자세·게임8방향 통합시트·오른쪽 보강을 확인. 수정본 main.py 표시창 재실행 후 제목/핸들/응답 확인
- 고정dt 캡처는 실제 main.run 키보드·실시간 성능·주관적 부드러움 검증과 구분. 사용자2차 확인은 마우스8방향 조준·걷기/정지/재출발·후진/옆걸음의 조준 유지·발 모양·그립·무게감

커밋: 범위 `a9058e7`, FR `3f5204c`, 나머지7/복원 `8a0c9e4`, 게임 통합 `aeff966`

검수 파일:

- `output/review/R1-C8-WALK/capture-complete.json`과 `qa-walk-방향-native.mp4`
- `output/review/R1-C8-WALK-director/audit.json`·`consistent-walk-preview.gif`
- `output/review/R1-C8-WALK-art/asset-check.json`·방향별 마스크/관절/1·5·idle 비교

재현: 기존 Sharp 환경에서 `node art/player/consistent-walk.cjs`. 게임은 `.\.venv\Scripts\python.exe -B game/main.py`. 새8PNG와 메타/테스트를 함께 유지
