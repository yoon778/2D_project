# R1-A UI·에셋 인계

기준일: 2026-11-04
상태: 2026-11-04 사용자 재개 후 지휘 확정 범위 UI-02/03만 수행했다. UI는 네이티브 창·화면·입력 도구를 사용하지 않고 dummy/모의 검사만 수행했다. core의 이동 알고리즘·API·에셋은 유지하고, 앱의 이벤트 폴링과 포커스 상실 시 누름 상태 초기화만 수정했다. 지휘 native 재검수 요청 후 정지하며 R1-B는 미착수다.

아래 구현·UI-01 수정·자체 검사 결과는 중단 전에 완료한 기록이다. 실제 조작·창 외형 등 미확인 항목은 미확인 상태로 유지한다. UI 자체 실행 창은 중단 전에 종료했다. 지휘의 native 창·입력 검수와 UI의 창 없는 재현을 구분하며 Git 조작은 하지 않는다.

## 변경 파일

- game/main.py: 1280×720 실행 창, 입력, 고정 투영·역변환, 지면·벽·발점·조준 표식, 깊이 정렬, 최소 smoke 옵션
- game/player_visual.py: 메타 기반 런타임 clip·배율·발점 보정, 한 방향 고정 이미지, 이미지 참조 해제
- game/assets/player/r1a-courier-20261104.png: 내장 imagegen으로 생성한 투명 전신 원본, 픽셀 무편집 복사
- game/assets/player/r1a-courier-20261104.prompt.txt: 정확한 생성 프롬프트
- game/assets/player/r1a-courier-20261104.json: 크기·clip·발점·표시 높이·출처·SHA256
- game/tests/test_visual_r1a.py: 투영·SDL 마우스·깊이·발점·메타 범위 검사 11개
- game/tests/test_visual_title.py: vendor FPS 제목 순간 노출 재현과 앱 raw poll 회귀
- game/tests/test_visual_input_r1a.py: 실제 main.run을 통과하는 SDL dummy 이벤트 재생·종료·자원 정리
- plans/handoffs/r1a-ui.md: 본 인계서

core.py·requirements.txt·다른 기획/발표 문서와 Git 인덱스는 수정하지 않았다. 현재 core의 고정 API를 import한다.

## 구현 결과

- 창 제목은 `Dead Route - R1-A`, 일반 실행은 즉시 장면을 표시한다. 별도 시작 메뉴가 없다.
- 지면은 960×720, `screen=(160+x,90+0.60*y)`이며 SDL 마우스 y는 먼저 `719-y`로 바꾼 뒤 역변환한다.
- 시작 발점은 (480,180), WASD는 core.move_player로 연결한다. 이동과 core.aim_player의 지면 조준은 독립이다. dt는 0.05초 이하이며 포커스가 없으면 이동 입력을 비우고 이동 dt=0을 전달한다.
- 벽은 Wall(400,330,220,60), 세운 높이 110px다. 높은 world.y부터 그리며 벽의 깊이 기준은 아래 밑변 y=330이다. 동률은 벽 다음 플레이어 순서다.
- 캐릭터는 한 방향·한 자세이며 회전·좌우 반전하지 않는다. 화면 상단에 한 방향 샘플 고정·조준 표식만 변화한다고 표시한다.
- 원본은 1254×1254 RGBA, 실제 알파 0–255다. 원본 해시와 게임 자원 복사본 해시가 일치한다.
- PNG 좌상단 기준 clip=(313,130,633,1055), 발점=(656,1129), 표시 clip 높이=120px다. 발점은 가까운 발 접지 후보 (516,1178)와 먼 발 (796,1080)의 중간점이다. 보이는 원본 높이는 약 119.5px이며 원본 자체는 리사이즈하지 않았다.
- 발점 메타는 고정 자세의 육안 후보다. 청록 십자가가 양발 사이 지면 중심에 놓이는지 실제 창에서 최종 확인해야 한다. 발의 크기가 같거나 두 발이 같은 화면 y에 있어야 한다는 뜻은 아니다.
- 한 번 로드한 PNG를 SDL에서 clip·축소하여 표시한다. 저알파 잔여가 있는 원본 외곽은 runtime clip으로 제외한다.
- 이미지 텍스처는 pico2d.Image 소멸자가 한 번 해제하고, 글꼴은 TTF_CloseFont 후 참조를 비운다. Renderer 초기화 실패 시 이미 만든 자원도 close 경로로 정리한다.

## 자체 확인 명령과 결과

일반 실행:

```powershell
.\.venv\Scripts\python.exe game/main.py
```

UI 좌표·깊이·발점 검사:

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s game/tests -p test_visual_r1a.py -v
```

결과: 11/11 통과. 지면 모서리·왕복·소수점·SDL y 반전, 벽 앞/뒤/동률·밑변 정렬·입력 무변조, 120px 배율·발점 정합·이동 불변성·실제 PNG와 메타 범위를 확인했다.

SDL dummy 자체 렌더:

```powershell
$env:SDL_VIDEODRIVER='dummy'
$env:SDL_AUDIODRIVER='dummy'
.\.venv\Scripts\python.exe game/main.py --smoke-test
```

결과: 종료 코드 0, 실제 SDL back buffer에서 아래 PNG 3장을 저장하고 직접 보았다. PNG 편집·합성으로 만든 검증 화면이 아니다. 이후 UI-01 확인에서 같은 파일을 Windows SDL 렌더 결과로 다시 저장했으므로 현재 PNG는 Windows 드라이버 실행의 back buffer다.

- output/review/R1-A/ui-initial.png — 발점 (480,180), 전신과 별도 조준 표식
- output/review/R1-A/ui-wall-behind.png — 발점 (480,420), 벽이 몸을 가리고 머리 일부가 위로 노출
- output/review/R1-A/ui-wall-front.png — 발점 (480,300), 캐릭터가 벽 앞에 표시

`--smoke-test`는 세 위치를 프로그램으로 배치하는 렌더 fixture다. WASD나 물리 마우스 입력을 검증하는 기능이 아니다. 일반 실행에서는 이 fixture를 사용하지 않는다.

문법 검사도 통과했다. 실제 창·입력·음향 판정과 자동 검사를 아래처럼 구분한다.

| 항목 | UI 자체 확인 |
| --- | --- |
| SDL dummy 렌더·PNG 시각 검토 | 완료 |
| 좌표·깊이·발점 자동 검사 | 11개 통과 |
| Windows SDL 창 생성·게임 프레임 제목 API | UI-01 프레임 끝 3/3은 순간 제목 경합을 검출하지 못했음. UI-02 Windows 재검수는 지휘 담당 |
| Windows 창 외형·OS 창 장식의 육안 확인 | 미확인, 지휘 1차 검수 필요 |
| 실제 WASD·마우스·포커스 복귀·Esc/닫기 조작 | 미확인 |
| 실제 청취 | 범위 밖, 오디오 기능 없음 |

## 지휘 1차 수정 UI-01

pico2d.get_events()의 FPS 표시가 창 제목을 덮어쓰는 문제를 지휘가 발견했다. 이벤트 처리 직후 `SDL_SetWindowTitle(..., b"Dead Route - R1-A")`를 다시 호출하도록 최소 수정했다.

검증은 `SDL_VIDEODRIVER=windows`, `SDL_AUDIODRIVER=dummy` 환경에서 main.run(smoke_test=True)를 실행하고 capture 훅에서 `SDL_GetWindowTitle(p.window) == b"Dead Route - R1-A"`를 검사했다. 세 실행 프레임 모두 통과했고 종료 코드 0으로 창을 닫았다. 이는 Windows SDL 창 생성·제목 API 검증이며 물리 입력이나 사람이 본 창 제목 검수를 대신하지 않는다.

첫 검사 훅은 pico2d.open_canvas 내부의 초기 Present에도 적용되어 실행 제목 설정 전 FPS 기본 제목으로 실패했다. 검사 시점을 앱 실행 프레임의 capture 직전으로 좁힌 후 3/3 통과했다. UI-01 당시 변경은 제목 복원 한 곳이었다. 이후 지휘의 실제 창 검수에서 FPS 제목이 반복 관찰되어 이 확인만으로 제목 안정성을 입증할 수 없었음이 확인되었다.

## 재개 후 입력 조사 — 수정 전

game/main.py의 실제 AST에서 이벤트 루프·포커스 초기화·축 계산·move_player 호출만 추출해 메모리에서 실행했다. pico2d/SDL 초기화·창·화면·OS 입력은 사용하지 않았다. dt=1/60초, 장애물 없는 지면에서 결과는 다음과 같다.

| 순서 | 재현 결과 |
| --- | --- |
| 같은 배치 D KEYDOWN→KEYUP | 최종 held가 비어 axis_x=0, 이동 0px |
| D KEYDOWN→빈 배치→빈 배치→KEYUP→빈 배치 | 앞 3프레임 각각 1.5px 이동, 해제 프레임부터 0px |
| D 유지→focused=False 프레임→focused=True | 포커스 상실 프레임에 held 초기화, 복귀 후 새 입력 없으면 0px |
| 프레임 사이에만 포커스 LOST→GAINED, KEYUP 없음·최종 focused=True | 기존 D가 유지되는 잠재 경로, 모델에서 1.5px 이동 |

설치된 pico2d 1.5.1 get_events()는 SDL_WINDOWEVENT와 repeat 키 이벤트를 반환하지 않는다. 따라서 마지막 포커스 경계 사례의 실제 발생 여부·KEYUP 전달 여부는 지휘의 raw SDL trace와 대조해야 한다. 같은 배치 짧은 탭도 이벤트가 앱에 도달한 뒤의 상태 샘플링 결과이며, 도구 입력이 미도달한 경우의 증거가 아니다.

이 조사에서 이벤트 처리 seam·입력 정책·게임 코드·테스트를 변경하지 않았다. 지휘 진단 후 필요한 최소 수정 범위를 합의한다.

지휘 native trace에서는 CUA w 입력 후 pico2d 필터를 거친 p.get_events 반환 KEYDOWN/KEYUP이 0개였다. 원시 SDL 큐 미도달이 확정된 것은 아니며, 같은 배치 DOWN/UP의 상태 샘플링 문제와도 구분해야 한다. 이 결과만으로 이동 코드를 추측 수정하지 않았다.

## 지휘 1차 수정 UI-02

원인: 설치된 pico2d.get_events()가 print_fps()로 FPS 제목을 쓴 뒤 SDL_Delay(1)를 호출한다. UI-01의 프레임 끝 제목 복원은 그 사이 약 1ms 노출을 막지 못한다.

수정 전 설치 모듈의 실제 get_events/print_fps를 호출하고 native setter·poll·delay만 mock한 재현에서, Delay(1) 시점은 `Pico2D Canvas (1280x720) 1.00 FPS`, 프레임 끝은 `Dead Route - R1-A`로 확인했다. 창·OS 입력을 사용하지 않았다.

UI-02의 초기 수정은 suppress_fps_title 컨텍스트로 run 동안 p.print_fps만 no-op로 바꾸고 종료 후 복원하는 방식이었다. 이후 UI-03에 포커스 사건 보존이 필요해져 아래 raw SDL poll로 통합했다. 최종 코드에서는 이 임시 컨텍스트를 필요한 부분만 정리하고 vendor 콜백 자체를 바꾸지 않는다. UI-01의 매프레임 제목 재설정도 제거하여 앱에서 제목을 초기 한 번만 쓴다. venv/vendor 파일은 수정하지 않았다.

SDL dummy에서 capture를 비활성화하고 세 프레임 실행한 결과: 전체 제목 쓰기는 `Dead Route - R1-A` 한 번, 이벤트 읽기 전후 제목 3/3 동일, FPS 함수 복원 확인, 종료 코드 0, 새 스크린샷 0장이다. 실제 Windows 창·AX·물리 입력 검수 결과로 해석하지 않는다.

## 지휘 1차 수정 UI-03

수정 전에 SDL dummy의 실제 큐에 SDL_PushEvent로 사건을 넣고 main.run(smoke_test=False)을 실행했다. Renderer의 원래 생성·draw·close를 그대로 호출하고, 그 경계에 관찰/사건 주입 wrapper만 붙였다. 마지막 포커스 flags를 True로 둔 상태에서 held W → 같은 배치 FOCUS_LOST·FOCUS_GAINED → 새 KEYDOWN 없음 회귀가 실패했다. 첫 프레임 y=181.5에서 다음 프레임 y=183.0으로 이동했으며 기대는 181.5 유지였다. 당시 입력 검사 5개 중 이 한 개만 빨간 회귀였다.

최소 수정은 main.poll_events()에서 새 SDL_Event를 매번 SDL_PollEvent로 읽어 raw 사건을 보존하는 것이다. 앱 루프는 raw key.keysym.sym·motion.x/y를 읽고 repeat 키는 기존처럼 제외하며 FOCUS_LOST를 받는 즉시 pressed를 비운다. 현재 flags=False일 때 비우는 기존 경로도 유지한다. p.get_events/print_fps를 호출하지 않아 FPS 제목 쓰기도 발생하지 않는다. core의 move_player·aim_player와 좌표/에셋 규격은 유지했다.

같은 배치 DOWN+UP의 이동 0은 회귀에서 기록만 했고 탭 보정 기능을 넣지 않았다. held 이동·KEYUP 후 정지·포커스 상실/복귀 후 정지·Esc/QUIT 종료를 실제 앱 루프에서 검증한다. Renderer 참조 해제·SDL video 종료·TTF 종료도 확인한다. 자동 큐 재생이며 실제 물리 입력 검증이 아니다.

최종 회귀 명령:

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s game/tests -p "test_visual*.py" -v
```

결과: **21/21 통과**. 기존 좌표·깊이·발점 11개, 제목 회귀 4개, 실제 main.run SDL dummy 재생 6개다. 입력 재생은 Renderer의 원래 생성·draw·close를 유지하며 결과를 관찰한다. 매 실행의 제목 쓰기 정확히 1회·print_fps/get_events 호출 0회, raw 마우스 조준과 플레이어 좌표 불변도 확인했다. 새 캡처는 만들지 않았다.

수정 후 포커스 회귀는 y=181.5에서 LOST+GAINED 이후 새 KEYDOWN 없이 그대로 정지한다. 정상 held 이동은 1/60초마다 1.5px, KEYUP 이후는 0px이며 같은 배치 DOWN+UP은 여전히 0px다. 이 결과는 SDL 큐 재생이 통과한 것이고 CUA·물리 키보드 전달을 입증하지 않는다.

지휘 native 추적은 이제 p.get_events 대신 main.poll_events의 raw 사건을 관찰해야 한다. 기존 p.get_events observer에 사건이 없는 것은 새 경로에서 정상이며 입력 미도달의 증거로 쓰면 안 된다. UI는 이 수정 단계에서 네이티브 창·GUI 입력·스크린샷을 사용하지 않았다.

UI-02/03 최종 변경은 main.py·test_visual_title.py·test_visual_input_r1a.py·본 보고서다. 코드 편집을 중지했으며 지휘의 실제 Windows 제목·raw 사건·물리 입력 재검수를 기다린다.

## 지휘·사용자 확인 항목

1. 일반 실행으로 1280×720 창과 `Dead Route - R1-A` 제목, 약 120px 캐릭터 크기를 확인한다.
2. 청록 발점이 양발 사이 접지 중심인지, 한 방향 고정 자세의 손·택배·방망이·가슴등과 사선 느낌을 확인한다.
3. WASD와 대각선 이동·벽 충돌, 마우스 표식과 발점의 관계를 확인한다. 몸이 마우스를 따라 돌지 않는 것은 R1-A의 의도된 범위다.
4. 벽을 우회해 뒤와 앞으로 이동할 때 몸의 앞뒤 가림이 바뀌는지 확인한다.
5. 창 전환 후 이동이 계속되지 않는지, Esc와 창 닫기가 정상 종료하는지 확인한다.

보행 프레임·4방향 전환·전투·빛·좀비·배달·메뉴는 구현하지 않았다. 사용자 확인 전 R1-B를 시작하지 않는다.
