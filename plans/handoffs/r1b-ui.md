# 1주차 R1-B UI·에셋 인계

## 현재 최종 인계 — 2026-11-05

**UI 소스·메타 변경 마무리 완료, 추가 편집·생성·실행 정지.** 파일명의 20261104는 작업 ID이며 독립 교정의 실제 수행일은 2026-11-05다. 프로젝트는 계속 1주차다. R1-B 사용자 2차 확인과 다음 진행 요청 전 R2를 시작하지 않는다.

- 지휘가 승인한 독립 교정 소스 game/assets/player/r1b-front-step-corrections-20261104.png를 채택했다. 실제 1774×887 RGBA, 887×887 두 셀이다. 정확한 입력은 같은 이름의 .prompt.txt에 보존했다.
- 앞·오른쪽 walk2는 viewer-left/방망이 아래 다리, 앞·왼쪽 walk2는 viewer-right/택배 아래 다리가 앞으로 나와 기존 walk1과 반대 지지가 확인된다. 기본 atlas의 나머지 10자세는 유지했다.
- sources에 atlas/front_steps를 등록하고 두 교정 frame만 front_steps를 선택한다. 모든 소스에 크기 검사·nearest·종료 정리를 적용하며, 로드 중 오류와 반복 close도 검사했다. PNG 합성·픽셀 후처리·반전·회전을 하지 않았다.
- 기본 atlas는 방향별 idle의 cell-local 몸/접지 루트를 공통으로 사용한다. 매 보행마다 가장 낮은 부츠나 양발 평균으로 root를 다시 정하지 않는다. 교정 두 자세는 모자 상단·가슴등 기준의 고정 배율/위치로 맞췄다. core의 충돌 발점·좌표 규격은 유지한다.

| 교정 자세 | source clip xywh | source pivot | 고정 scale_reference_height |
| --- | --- | --- | ---: |
| front_right walk2 | (213,98,449,722) | (452,775) | 702.472021 |
| front_left walk2 | (1096,104,418,716) | (1312,749) | 665.127547 |

표시 배율은 128/고정 reference height다. 교정 frame의 전체 bbox를 매번 128px로 정규화하지 않으며 기존 idle과 머리·흉부 크기를 맞춘다. 정확한 모자·어깨·택배 모양의 픽셀 동일성을 보증하는 것은 아니다.

자체 전체 회귀 명령 `.\.venv\Scripts\python.exe -B -m unittest discover -s game/tests -q`는 **66/66 통과**했다. 소스별 셀/clip/피벗·선택 이미지·고정 배율·Nearest·단일 해제·오류 정리까지 포함한다.

최종 SDL dummy contact sheet: output/review/R1-B/two-source-contact-sheet.png. 직접 검토했으며 정렬 관찰값은 output/review/R1-B/two-source-alignment.json에 저장했다. 동일 방향 idle/walk의 발점 기준 clip 상단 높이 차이는 front_right **0.539px**, back_right **0px**, back_left **0px**, front_left **0.527px**로 모두 3px 이내다. 이는 메타/렌더 경계 기준 수치이며 실제 보행 체감은 사용자 확인 대상이다.

지휘 전달 결과: 지휘가 전체 66개를 별도로 실행하고 최신 native_review.py의 Windows contact sheet·벽 앞뒤 캡처를 직접 검토하여 앞 방향 반대 발 교대·상체 정렬·장비 손·가림을 확인했다. 이 native 결과는 지휘의 검수이며 UI가 네이티브 창/GUI 입력을 사용한 것으로 기록하지 않는다.

현재는 지휘 문서·주차 표기 중간 커밋·사용자 2차 인계 대기다. 물리 키보드 검증을 새로 통과 처리하지 않았다. Git은 지휘만 수행한다.

## 최초 아틀라스·실패 교정 검토 이력 — 아래는 당시 기록

기준일: 2026-11-04
상태: 코드 연결·자동 검사까지 수행 후 정지. **front_right/front_left의 반대 발 교대 시각 검수 미통과**로 R1-B 완료가 아니다. 지휘가 두 원본과 메타를 비교해 추가 교정 범위를 결정한다. 추가 생성·native 창·GUI·Git 조작은 하지 않는다.

## 실제 원본과 선택 상태

1. 최초 12셀 원본: game/assets/player/r1b-courier-atlas-20261104.png
   - 도구 출력: C:/Users/cys04/.codex/generated_images/01a19ece-e348-7db1-ba4e-4076a3f16a0f/exec-ae99a438-137e-4a5c-b6f4-b7335d91ac27.png
   - 현재 runtime canonical PNG다. 연결 검수용으로 선택했다는 뜻이며 시각 검수 통과를 뜻하지 않는다.
   - SHA256: CE8C0AC85DAA5B7F8AEBF44464B858DB0BC192D4A838A493F774799690D24981
2. 지휘 요청 표적 수정 원본:
   - C:/Users/cys04/.codex/generated_images/01a19ece-e348-7db1-ba4e-4076a3f16a0f/exec-5b8fb5e0-6065-430c-8f80-0daa144d1276.png
   - 1행·4행의 3열 하체만 반대 지지발로 고치도록 요청했으나 성공 판정하지 못했다. game/assets에 중복 복사하거나 runtime으로 선택하지 않았다.

내장 imagegen 최초 생성 1회·지휘 승인 표적 편집 1회다. 두 정확한 입력은 r1b-courier-atlas-20261104.prompt.txt에서 구분해 보존했고 선택 여부·출처·제한을 JSON에 기록했다. PNG의 프로그램 후처리·다리 재그리기·전체 회전·좌우 반전은 하지 않았다.

## 이번 변경 파일

- game/main.py: 실제 이동 전후 dx/dy와 갱신된 aim을 PlayerVisual.update에 전달, 제목·안내·smoke 경로 R1-B 갱신
- game/player_visual.py: 로직 담당의 실제 Locomotion 사용, 방향별 idle 기준 공통 배율로 프레임 clip/발점 렌더
- game/assets/player/r1b-courier-atlas-20261104.png/.json/.prompt.txt
- game/tests/test_visual_input_r1a.py·test_visual_title.py: 기존 검사를 유지하고 제목 기대값만 R1-B로 변경
- game/tests/test_visual_locomotion_r1b.py: 실제 앱 루프의 update 연결 6개 검사
- game/tests/test_visual_atlas_r1b.py: 12셀·프레임 선택·발점·공통 배율·draw 무변조 4개 검사
- plans/handoffs/r1b-ui.md: 본 보고서

core.py·locomotion.py·공용 문서·기존 R1-A 참조 PNG/JSON/prompt는 UI가 수정하지 않았다.

## 연결 규격

- move_player 전후 실제 좌표 차이를 dx/dy로 구한다. smoke 위치 강제 배치는 이 차이에 넣지 않는다.
- aim_player 갱신 뒤 PlayerVisual.update(aim_angle,dx,dy)를 한 번 호출하고 기존 draw(foot_x,foot_y)를 사용한다.
- Locomotion.facing/frame_index가 atlas의 방향과 idle/walk1/walk2를 고른다. 벽 앞·KEYUP·포커스 상실 시 실제 dx/dy가 0이면 idle이다.
- 조준각·표식은 연속이며 이동 방향으로 몸을 돌리지 않는다. 후진·옆걸음도 실제 거리만 위상에 반영한다.
- 각 방향의 scale은 128/해당 idle source 높이다. 보행 프레임마다 bbox 높이를 128로 정규화하지 않는다.
- 원본은 실제 1086×1448 RGBA, 3열×4행의 셀은 362×362다. 네이티브 64px 격자 원본이 아니다.
- nearest·기존 raw SDL 입력·포커스 초기화·Esc/QUIT·자원 정리·지면 좌표·벽 배치·90px/s를 유지한다.

## 메타와 시각 검토

각 값은 PNG 좌상단 기준이다. clip은 xywh, pivot은 원본 전역 px다. 발점은 양발 외곽으로 추정한 접지 중간점 후보이며 최종 확정값이 아니다.

| 방향 | 프레임 | clip | pivot |
| --- | --- | --- | --- |
| front_right | idle | (87,30,204,312) | (194,332) |
| front_right | walk1 | (449,30,202,312) | (553,329) |
| front_right | walk2 | (811,30,202,312) | (917,320) |
| back_right | idle | (98,389,190,313) | (182,694) |
| back_right | walk1 | (462,389,189,303) | (540,676) |
| back_right | walk2 | (824,389,189,314) | (900,679) |
| back_left | idle | (95,752,188,311) | (189,1054) |
| back_left | walk1 | (458,752,188,312) | (550,1043) |
| back_left | walk2 | (821,752,186,311) | (907,1038) |
| front_left | idle | (83,1114,186,306) | (180,1412) |
| front_left | walk1 | (440,1115,191,306) | (550,1398) |
| front_left | walk2 | (809,1115,184,309) | (918,1398) |

12셀이 실제로 있으며 4방향 앞/등·장비·도트풍은 확인했다. 그러나 front_right/front_left에서 walk1·walk2가 같은 쪽 발을 내민 듯 보여 반대 발 교대 통과로 처리하지 않는다. 표적 수정본도 명확한 개선이 없었다. back_right는 교대가 보이며 back_left는 실루엣 차이가 있지만 겹치는 다리의 좌우 판별은 제한된다. 지휘의 원본 비교 결과를 우선한다.

실제 공통 배율 렌더에서 발점부터 clip 상단까지의 높이 변동은 front_right 4.93px·back_right 7.36px·back_left 6.59px·front_left 6.27px다. 프레임별 배율 변화로 인한 크기 펌핑은 아니지만 접지 피벗·자세에 따른 상체 들썩임은 추가 시각 검토가 필요하다. 숫자를 맞추기 위해 단순 스프라이트 상하 흔들기를 넣지 않았다.

최초 원본의 알파 1–16 잔여가 163,307px이며 일부 가장자리 색 번짐이 있다. runtime clip은 빈 여백 일부를 제외하지만 셀 안의 색 번짐까지 제거한 것은 아니다. 128px contact sheet에서는 큰 배경 상자는 보이지 않았다.

## 자체 확인

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s game/tests -q
```

**63/63 통과**. 로직 담당 모듈을 사용하며 임시 대체 모듈을 만들지 않았다. 자동 검사는 프레임 선택·좌표·배율·실제 main.run 전달을 검증하며 그림 속 실제 반대 발 전진을 보증하지 않는다.

실제 앱 루프의 SDL dummy 재생에서 held/KEYUP·같은 배치 focus loss/gain·벽 접촉 무변위·마우스 방향·후진/옆걸음·smoke 강제 배치 제외를 확인했다. 원래 Renderer와 업데이트를 유지하는 관찰 wrapper이며 단순 helper 호출을 앱 루프 검증으로 바꾸어 표현하지 않았다.

SDL_VIDEODRIVER=dummy·SDL_AUDIODRIVER=dummy·SDL_RENDER_DRIVER=software로 main.run(smoke_test=True)와 대표 자세 fixture를 실행했다.

- output/review/R1-B/ui-initial.png·ui-wall-behind.png·ui-wall-front.png: 실제 main.run smoke 3장
- output/review/R1-B/{front_right,back_right,back_left,front_left}-{0,1,2}.png: 각 방향 idle·walk1·walk2 실제 SDL 12장
- output/review/R1-B/atlas-runtime-contact-sheet.png: 같은 발점에 128px로 그린 12자세 접촉 시트, 직접 검토
- output/review/R1-B/pose-review.json: 방향·프레임·공통 배율·발점 기준 상단 높이 관찰값

자세 fixture는 update에 이동 거리 0·8·16px를 순차로 넣어 idle·phase0.25·phase0.75를 고른 것이며 물리 입력이나 실제 플레이 이동 검증이 아니다. 이번 UI 작업에서는 native 창·GUI·사용자 키보드·청취를 확인하지 않았다.

## 남은 지휘 판단과 정지

1. 최초/표적 수정 원본을 비교하고 front_right/front_left 반대 발 교대 교정 범위를 결정한다.
2. 발점 후보와 4.93–7.36px 상체 높이 변동을 실제 렌더에서 확인한다.
3. 아트 교정 후 필요한 메타 갱신·회귀·native 검수를 거친다. 현재 상태를 R1-B 완료나 사용자 2차 통과로 기록하지 않는다.

추가 생성·코드 편집을 멈추고 지휘 지시를 기다린다. R2·좀비·전투·빛·8방향·메뉴는 착수하지 않았다. Git은 지휘만 수행한다.
