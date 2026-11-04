# 1주차 R1-B-S1 지휘 검수

기준일: 2026-11-05 · 상태: 지휘 1차 검수 통과, 사용자 2차 확인 대기
기준: [한 방향 개선 계약](../r1b-smooth-contract.md)

## 배정·수정·커밋

- 사용자 요청으로 front_right 한 방향 보행을 2장→8장으로 개선
- 로직 채팅: 장수별 순수 자세 선택, 2장 호환·거리 분할 경계 보정
- UI·에셋 채팅: 8장 제작·소스/발 root·게임 연결·자동 회귀
- 첫 그림은 같은 다리의 반주기를 반복해 미채택, 표적 교정 1회 후 1/5번의 반대 다리 전진을 지휘 확인
- 공통 배율·몸 root로 상체를 정렬. 기존 idle·다른 세 방향 프레임 사전·기존 PNG 3개는 baseline 3f9620c와 정확히 일치
- `7eaf4c8`: 계약 확정
- `7106d01`: 21개 집중 검사·독립 검토를 통과한 자세 선택
- `ef5b08f`: 앞·오른쪽 보행 8장·게임 연결·메타/회귀 적용

## 실제 검수

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s game/tests -q
.\.venv\Scripts\python.exe -m compileall -q game
.\.venv\Scripts\python.exe -B output/review/R1-B-S1/smooth_native_review.py
```

- 전체 **74/74 통과**, compileall 종료 코드 0
- 실제 main.run SDL dummy 사건 재생: 8장 선택, 키 해제·포커스·벽 앞 idle·마우스·후진/옆걸음·종료 회귀
- 세 텍스처 canvas/nearest·종료/오류 정리, 18프레임 clip/cell/root·고정 배율 검사
- 독립 코드/메타 검토: 추가 blocker 없음
- 숨김 **Windows SDL** 실제 게임 렌더로 4장: idle+8보행 contact sheet, 다른 세 방향 시트, 벽 앞/뒤
- 지휘가 8장 시간순 자세·좌우 반주기·머리/몸/장비·8→1 경계 캡처·벽 앞뒤 가림 직접 이미지 검토
- 목표 방향 머리 높이 차이 **0.1554px**. clip 상단 기준 보조 수치이며 해부학/자연스러움 전체를 보증하는 값이 아님
- 실제 core 이동→조준→visual 갱신→게임 렌더 60프레임: 조준 방향으로 2초·180px 전진, 8자세 모두 선택
- 이동 90px/s·32px 주기 유지. 검수 영상은 **1280×720·30FPS·60프레임·2초**, FFmpeg 인코딩·전체 디코드와 ffprobe 확인
- 최종 메타 수신 후 native fixture 재실행, 검수 중 PNG/메타 SHA256 보존·SDL 완전 종료 확인

검수 자료는 Git 제외 폴더 output/review/R1-B-S1/에 저장
주요 파일: smooth-contact-sheet.png, smooth-other-facing-regression.png, smooth-wall-front.png, smooth-wall-behind.png, smooth-native-review.json, sequence/frame-*.png, smooth-walk-native.mp4
보기 편한 smooth-walk-closeup.mp4는 위 게임 렌더 영상의 320×320 영역을 nearest로 2배 확대한 로컬 미리보기이며 별도 게임 에셋이 아님. 디코드 오류 없음
검수용 fixture의 시간·거리 입력은 사용자 키보드나 main.run 실행을 뜻하지 않음. 실제 앱 연결은 별도 dummy 회귀로 검사함

## 한계·사용자 2차 확인

프레임 3/7의 가려진 무릎·고관절과 4/8의 비슷한 부츠 실루엣, 생성 그림의 세부 차이는 남음
새 PNG에 낮은 알파 가장자리 잔여가 있으며 정확한 64px 원본 격자가 아님
연속 재생의 주관적 부드러움·실제 조작감·발 미끄러짐 체감은 사용자 2차 확인 필요

프로젝트 루트에서 실행:

```powershell
.\.venv\Scripts\python.exe game/main.py
```

1. 마우스를 앞·오른쪽으로 두고 WASD로 걸으며 8장 보행·주기 이음새 확인
2. 정지/재출발·벽 접촉 때 보행 정지 확인
3. 후진·옆걸음의 발 움직임과 몸/택배 크기 확인
4. 다른 세 방향의 기존 2장 보행과 비교해 품질 의견 전달

게임 창은 검수 후 종료. 사용자 확인 전 다른 방향 확장·R2 전투 미착수, 푸시 미실행
