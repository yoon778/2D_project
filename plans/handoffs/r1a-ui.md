# R1-A UI·에셋 인계

기준일: 2026-11-04
상태: 2026-11-04 사용자 컴퓨터 사용 요청으로 즉시 중단. 네이티브 창 실행·자동 입력·스크린샷·추가 구현·검수를 진행하지 않는다. 사용자 재개 지시를 지휘가 전달하기 전까지 대기한다.

아래 구현·UI-01 수정·자체 검사 결과는 중단 전에 완료한 기록이다. 실제 조작·창 외형 등 미확인 항목은 미확인 상태로 유지한다. UI 자체 실행 창은 이미 종료했으며 지휘가 띄운 검수 창의 종료는 지휘가 담당한다. 다른 묶음은 미착수이며 Git 조작은 하지 않았다.

## 변경 파일

- game/main.py: 1280×720 실행 창, 입력, 고정 투영·역변환, 지면·벽·발점·조준 표식, 깊이 정렬, 최소 smoke 옵션
- game/player_visual.py: 메타 기반 런타임 clip·배율·발점 보정, 한 방향 고정 이미지, 이미지 참조 해제
- game/assets/player/r1a-courier-20261104.png: 내장 imagegen으로 생성한 투명 전신 원본, 픽셀 무편집 복사
- game/assets/player/r1a-courier-20261104.prompt.txt: 정확한 생성 프롬프트
- game/assets/player/r1a-courier-20261104.json: 크기·clip·발점·표시 높이·출처·SHA256
- game/tests/test_visual_r1a.py: 투영·SDL 마우스·깊이·발점·메타 범위 검사 11개
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
| Windows SDL 창 생성·게임 프레임 제목 API | UI-01에서 생성 성공·제목 3/3 통과, 창 종료 완료 |
| Windows 창 외형·OS 창 장식의 육안 확인 | 미확인, 지휘 1차 검수 필요 |
| 실제 WASD·마우스·포커스 복귀·Esc/닫기 조작 | 미확인 |
| 실제 청취 | 범위 밖, 오디오 기능 없음 |

## 지휘 1차 수정 UI-01

pico2d.get_events()의 FPS 표시가 창 제목을 덮어쓰는 문제를 지휘가 발견했다. 이벤트 처리 직후 `SDL_SetWindowTitle(..., b"Dead Route - R1-A")`를 다시 호출하도록 최소 수정했다.

검증은 `SDL_VIDEODRIVER=windows`, `SDL_AUDIODRIVER=dummy` 환경에서 main.run(smoke_test=True)를 실행하고 capture 훅에서 `SDL_GetWindowTitle(p.window) == b"Dead Route - R1-A"`를 검사했다. 세 실행 프레임 모두 통과했고 종료 코드 0으로 창을 닫았다. 이는 Windows SDL 창 생성·제목 API 검증이며 물리 입력이나 사람이 본 창 제목 검수를 대신하지 않는다.

첫 검사 훅은 pico2d.open_canvas 내부의 초기 Present에도 적용되어 실행 제목 설정 전 FPS 기본 제목으로 실패했다. 검사 시점을 앱 실행 프레임의 capture 직전으로 좁힌 후 3/3 통과했다. 애플리케이션 코드 추가 변경은 위 제목 복원 한 곳뿐이다.

## 지휘·사용자 확인 항목

1. 일반 실행으로 1280×720 창과 `Dead Route - R1-A` 제목, 약 120px 캐릭터 크기를 확인한다.
2. 청록 발점이 양발 사이 접지 중심인지, 한 방향 고정 자세의 손·택배·방망이·가슴등과 사선 느낌을 확인한다.
3. WASD와 대각선 이동·벽 충돌, 마우스 표식과 발점의 관계를 확인한다. 몸이 마우스를 따라 돌지 않는 것은 R1-A의 의도된 범위다.
4. 벽을 우회해 뒤와 앞으로 이동할 때 몸의 앞뒤 가림이 바뀌는지 확인한다.
5. 창 전환 후 이동이 계속되지 않는지, Esc와 창 닫기가 정상 종료하는지 확인한다.

보행 프레임·4방향 전환·전투·빛·좀비·배달·메뉴는 구현하지 않았다. 사용자 확인 전 R1-B를 시작하지 않는다.
