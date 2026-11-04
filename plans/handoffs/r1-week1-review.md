# 1주차 R1 전체 실행 품질 검수

기준일: 2026-11-05
상태: 1주차 R1 개발·지휘 통합/모션/실측 프레임/자원 검수 통과, 사용자 2차 확인 대기
사용자 1주차 전체 순차 마무리 요청과 [검수 계약](../r1-week1-validation.md)을 따름

## 1주차 구현·검수 범위

- 고정 사선 2.5D 장면·플레이어·벽1개·지면↔화면 조준·깊이 정렬
- WASD 90px/s·대각 정규화·원형 충돌 반경14·벽 접근/미끄러짐/후퇴·월드 경계
- 마우스 조준과 이동 분리, 네 방향 모두 idle1+walk8의36자세·32px 실제 거리 주기
- 정지·벽 접촉·포커스 해제 시 idle, 후진/옆걸음·방향 변경 위상 유지
- raw SDL 사건·제목 유지·Esc/QUIT·리소스 정리
- 전투·좀비·빛·배달은 원래 2주차 이후 단계, 이번 구현 범위에 포함하지 않음

전체 자동79개·compileall 통과, 실제 main.run SDL dummy 입력 회귀 포함
[S2 기록](r1b-smooth-s2-review.md)에 방향별 제작·수정·커밋·Windows 렌더·baseline 보존·시각 검토를 저장
최종 네 방향 Windows fixture는 방향별4장/60프레임이며 고정 dt 캡처와 실측 성능을 구분함

## 실제 main.run 성능 측정

실제 perf_counter/dt·원래 sync=True·SDL_RenderPresent를 유지함. 영상 FPS·고정 dt·수동 sleep으로 측정값을 만들지 않음
2초 warmup 후30초, 입력은 실제 SDL 큐 사건 재생. 측정 중 캡처·디스크 쓰기 없음
동일 Windows/direct3d renderer flags14(vsync=True), OS 보고 디스플레이240Hz 환경

| 항목 | 숨김 창 | 표시된 게임 창 |
| --- | ---: | ---: |
| 측정 시간 | 30.0011초 | 30.0010초 |
| 측정 프레임 | 966 | 7,194 |
| 입력 포커스 | 숨김 surrogate | 실제 SDL window flags |
| update/draw 근사 p95 | 3.6832ms | 2.6154ms |
| Present 호출 p95 | 30.8110ms | 2.2157ms |
| 프레임 간격 median | 33.1120ms | 4.1706ms |
| 프레임 간격 p95 / p99 | 34.0504 / 34.4397ms | 4.4359 / 4.5637ms |
| 프레임 간격 max | 35.4062ms | 12.1026ms |
| 50ms 초과 | 0회 | 0회 |

표시창은 약239.8FPS. 이 측정의 모든 프레임 간격이60FPS 예산16.67ms 이내였음
숨김/표시 상태의 Present 대기 차이를 관찰했으며 숨김 결과만으로 게임 코드의30FPS 문제라고 판정하지 않음
측정된 작업 시간은 wall-clock 근사값으로 입력 adapter 비용도 포함하며 순수 CPU/GPU 실행 시간과 다름

두 실행 모두 startup 이미지6·폰트1, 프레임 중 이미지/폰트 재로드0, SDL_WasInit(0)==0 확인
표시창의 이동 trace에서4방향·이동26개·idle6개 표본 확인. 사용자 키보드 입력은 아님
CUA로 실제 게임 창 제목·포커스·자동 종료를 관찰. 자동 종료 후 픽셀 snapshot은 얻지 못해 CUA 화면 캡처 통과로 기록하지 않음

증거: output/review/R1-week1/runtime-quick.json, runtime-visible.json, runtime_quick.py

## 필요한 스킬

- session-defaults로 기존 스킬의 범위를 확인. 웹 benchmark와 Windows UIA는 현재 SDL 측정에 맞지 않아 적용하지 않음
- skill-creator로 로컬 C:/Users/cys04/.codex/skills/pico2d-native-qa/SKILL.md 생성
- 공식 quick_validate 통과, 독립 사용 시나리오 검토에서 잘못된 검수 판정 유도 없음
- 전용 skill과 verification-before-completion 기준 적용. 검증기 PyYAML은 별도 skill-runtimes 폴더에만 설치

## native 입력·재시작·자원 추가 확인

runtime_qa.py의 실제 main.run 3회: measured_quit, restart_escape, restart_quit 모두 passed·problems[]
숨김 focus surrogate·실제 SDL 큐 focus 사건으로 검사하며 OS 창 전환/물리 키보드를 대신한 결과가 아님

- 벽 아래/위 접촉·우회·대각 이동·조준 경계·키 해제·focus lost/regain 후 새 keydown·정지/재출발 확인
- 네 방향에서 보행1..8 전부 관찰, 첫 장기 실행에서 이동 후 정지408개 표본 확인
- 세 실행 모두 이미지6/폰트1 startup 로드, 프레임 중 재로드0
- 첫 실행 텍스처6,851개 생성/해제 일치(글자 임시 텍스처 포함), 후속121/71개도 일치
- 세 실행 모두 추적 texture/font/chunk/renderer/window live0, Renderer.close1회, SDL_WasInit(0)==0
- 측정 중50ms dt clamp0, 게임 소스/메타/PNG SHA256 보존
- 증거 output/review/R1-week1/runtime-qa-result.json. 이 숨김 실행의 timing은 표시창 성능 수치와 구분

재현된 게임 코드 오류가 없어 성능/아키텍처를 임의 변경하지 않음. 변경은 모션 에셋/연결 메타·의미 있는 회귀 검사·검수 문서에 한정

## 마무리·사용자 확인

현재 장면·현재 PC의 결과이며 향후 전투/맵 부하나 사용자 주관적 부드러움을 미리 보증하지 않음

사용자 실제 WASD·마우스·창 전환·보행 체감 확인은 마지막2차 검수로 남음
프로젝트 루트에서 실행:

```powershell
.\.venv\Scripts\python.exe game/main.py
```

확인 항목: 네 방향 걷기·후진/옆걸음·정지/재출발·몸/장비 크기·벽 앞뒤 가림·다른 창 전환 뒤 입력 해제
1주차 검수 종료 후 R2는 다음 진행 요청 전 착수 금지, 푸시 미실행
