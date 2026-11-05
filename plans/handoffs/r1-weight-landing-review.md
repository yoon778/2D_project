# 1주차 R1-W2 착지·상체 보완 검수

기준일: 2026-11-05 · baseline 05f55ed
상태: 앞·오른쪽8장 적용·지휘 기술 검수 통과, 사용자2차 체감 비교 대기
기준: [W2 계약](../r1-weight-landing-contract.md), 이전 [W1 시안](r1-weight-review.md)

## 수행·수정

- 사용자 속도 유지 선택에 따라90px/s·32px 거리 주기·균등8위상 보존. 한 주기 약0.35556초·자세당 약44.44ms이며 착지 체류 시간을 늘린 작업은 아님
- 로직 담당은 엔진4파일 SHA·정지/벽/방향전환과 시간 한계를 검토, UI는 front_right8장만 새 landing_front_right 시트로 연결
- 최초 후보는 무릎/골반 압축이 보였으나 cap 상단 범위20sourcepx·반주기 교대가 모호해 미채택
- 표적교정1도16sourcepx 범위로 과도한 하강·같은 다리 선행이 남아 미채택. 지휘와 독립 리뷰가5/6의 반대 지지를 재요청
- 표적교정2에서 얕은2/6과5/6 방망이측 지지 복원 확인. 원본 자체 관절 그림 교정이며 PNG 전체 이동/회전·프레임별 배율/피벗 보정 없음
- 새1774×887 RGBA 원본 SHA256: 27DCBFB0004DC06943CB15A7DC3F279167EE84002D6FF066235949DA7EE562D8
- 공통 reference385.036988·scale≈0.332435594473·cell-local root=[215.98656,386.727873],8장 동일 적용
- 계약 커밋 `0fb5766`, 원본/메타/보존 회귀/담당 보고 커밋 `59b463c`

## 지휘 실제 검수

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s game/tests -q
.\.venv\Scripts\python.exe -m compileall -q game
.\.venv\Scripts\python.exe -B output/review/R1-W2/check_baseline.py
.\.venv\Scripts\python.exe -B output/review/R1-W2/native_review.py --direction front_right
```

- 지휘 전체79/79·compileall 통과. UI의 집중8개/dummy 결과와 별도 실행
- baseline 메타 중 기존7source사전·모든idle·다른3방향 frames와 기존PNG/프롬프트8개·엔진4파일 정확 보존, 모든 PNG 선언 SHA 일치
- 최종36자세·8소스, 기존 실제 frame 선택·셀/clip/공통root/고정배율·nearest/canvas·다중소스 해제 검사 유지. 독립 메타/테스트 리뷰 blocker 없음
- Windows 숨김 SDL 실제 Renderer/core로4장 정지 시트·실제 변위 연동60프레임 캡처, 검수 중 PNG/메타 SHA 불변·종료 SDL 잔여0
- 지휘가 선택 raw·dummy/Windows 실제128px 시트·다른3방향과4→5/8→1 경계 프레임을 직접 확인. 낮은 부츠·1/5 지지 반전·얕은 무릎 변화·장비 손/크기 유지, 상체 변화는 작음
- Windows cap 상단 proxy 범위1.994613567px로3px 상한 이내. 1→2 하강≈0.664871px,5→6≈1.662178px. 양쪽이 각각2px 내려앉는 목표를 달성한 수치가 아님
- 기존 W1 네이티브 영상이 baseline과 같은 메타/엔진을 사용함을 확인해 전후 비교에 사용. 같은90/32 조건·2초/60프레임을 동일 crop/nearest2배 확대·좌우 배치, FFmpeg 전체 디코드 통과
- 캡처30FPS는 앱 성능 측정 아님. 이번 단계에서 actual main.run·물리 입력·실제 FPS를 새로 측정하지 않았으며 이전 약240FPS 수치는 [1주차 baseline 이력](r1-week1-review.md)으로만 보존

로컬 근거: output/review/R1-W2/baseline.json, baseline-preservation.json, front_right/native-review.json, front_right/native-contact-sheet.png, before-native.mp4, after-native.mp4, landing-walk-comparison.mp4
담당별 작업/한계: [로직](r1-weight-landing-logic.md)·[UI](r1-weight-landing-ui.md)

## 한계·사용자2차

관절 윤곽 변화는 보이지만2/6 눌림은 작고 비대칭, 상체·상자 받침 차이도 미세함. 4/8 전진은 유사하며 발 전환/미끄러짐·연속 재생의 무게감은 사용자 비교 대상. 머리 상단 수치는 골반/가슴 하중 측정이나 월드 지지발 고정 보증이 아님

전후 영상 왼쪽은 W1, 오른쪽은 W2. 동일 속도에서 착지 버팀·상체의 작은 눌림·반복 연결 비교
프로젝트 루트에서 `.\.venv\Scripts\python.exe game/main.py` 실행 후 앞·오른쪽 조준으로 걷기/후진/옆걸음·정지/재출발 확인
지휘 기술 검수/커밋 후 사용자2차 확인 대기. 다른3방향 확대·R2·푸시는 미착수
