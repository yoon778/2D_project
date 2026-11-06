# R2-FR12 UI·에셋 인계 — 2026-11-06

기준선 `9f33924`, 계약 `plans/r2fr-smooth-contract.md`. 앞·오른쪽 공격을 기존6자세에서 실제12자세로 연결했다. 지휘 첫 시안 검수 양호 회신, 추가 미술 교정 요청 없음. 담당파일·그림 동결 상태다.

## 변경

- 기존 `art/player/r2a-combat-assets.cjs`: 준비/타격/후속/회복 사이 중간 자세와 복귀 중간2장 추가. 기존 파일명·소스명을 유지한다
- FR 정지 PNG384×288·12장, 이동 PNG768×1152·96장. 기존 전투JSON의 `attack`·`attack_walk`2블록만 변경
- 정확한 경계: 0/.045/.09/.135/.18/.225/.27/.32/.37/.425/.48/.54/.60초
- 팔은 각 뼈의 짧은 각도 경로와 투영 길이를 보간한다. 손·방망이도 짧은 회전 경로를 사용하며 같은 그립에 연결한다. 좌표만 직선 보간해 중간 팔 길이가 줄어드는 방식을 피했다
- 기존 키는 신규 index0/2/4/6/8, 원본 복귀는11. .425/.48의 중간 자세를 거쳐 .54에 원본으로 복귀한다
- 새 검사 `art/player/check-r2fr-smooth.cjs`. 기존 C8 검사는 이번 FR2소스만 예외로 좁히고 다른15소스/메타와 C8 제작 입력의 기준선 비교를 강화했다
- Python·R1·다른7뷰 제작도구/설정·생산4파일 수정, Git 작업 없음. 공유 트리의 Python 검사 변경은 로직 담당 소유다

## 에셋 검사

`node art/player/check-r2fr-smooth.cjs` 통과:

- 108셀: 정지12장·이동96장 모두 고유. 보행8위상 각각12자세 고유
- 기존6키의 정지6셀·이동48셀 총54셀 RGBA 완전 일치
- 마지막 정지1+이동8, 총9셀은 FR R1 원본의 (8,8) 패딩과 RGBA 완전 일치
- 머리 원본32724픽셀 일치. 중간 alpha·승인 팔레트 이탈·셀 가장자리·8연결1~2픽셀 고립 성분 모두0
- 중간6자세×2뼈의 투영 길이가 양끝 키 길이 범위 안에 있음
- 메타12경계·clip·피벗(48,80)·기준64·2배·이동 인덱스·attack_steps12/walk_phases8 일치

`node art/player/check-r2c8-combat.cjs` 통과:

- 다른7방향14소스378자세·315활성자세·63복귀 및 기존8잔여 좌표 회귀 유지
- 다른7뷰14PNG·좀비PNG·15메타블록, R1 전체 입력/에셋, 고정 생산4파일 기준선 불변
- C8 require 출력·리소스 변경0. FR 변경 예외 외의 이전 검사 기준 유지

제작 명령3경로를 각각 재실행한 뒤 현재 전투 PNG17개 바이트·메타17블록·실제12키 `arm-poses.json` 모두 동일 확인:

1. `node art/player/r2a-combat-assets.cjs`
2. `node art/player/r2a-combat-assets.cjs --attack-walk-only`
3. `node art/player/r2c8-combat-assets.cjs`

## 검수 자료

출력 `output/review/R2-FR12-art/`:

- `attack-12poses-4x.png`: 실제12자세, 시간순4열×3행
- `previous-six-vs-new-keys-3x.png`: 위 기존6키, 아래 신규 대응6키
- `attack-walk-sequence-4x.png`·`sequence.json`: 시간순 이동 시안
- `attack-walk-96-2x.png`: 전체12×8보행
- `arm-poses.json`: 실제 제작에 사용한12자세 좌표·손/무기 각도·그립
- `asset-check.json`·`rebuild-check.json`: 최종 검사 수치와3경로 재생성 결과
- `previous/`: 변경 직전 FR2PNG와 전투 메타 비교 원본

오프라인 PNG 검사와 지휘 첫 시안 검수 결과다. 실제 Windows SDL·물리 입력·플레이 체감·실시간 성능 완료로 확대하지 않는다. 추가 프레임/방향 제작 없이 지휘 통합 검수·사용자2차 확인을 기다린다.
