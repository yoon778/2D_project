# 1주차 R1-B 로직 인계

기준일: 2026-11-04
상태: 자체 확인 완료, 지휘 1차 검수 요청 후 정지
기준: [R1-B 연결 규격](../r1b-contract.md)

## 변경 파일

- [game/locomotion.py](../../game/locomotion.py): 순수 방향 선택·거리 기반 보행 상태
- [game/tests/test_locomotion.py](../../game/tests/test_locomotion.py): 공개 API 테스트 15개
- 이 보고서

core·SDL·화면·에셋·main·공용 문서와 Git은 변경하지 않음

## 구현 결과와 연결

- `STRIDE_DISTANCE=32.0`, `select_facing(aim_angle, current=None)`, `Locomotion(facing="front_right", phase=0.0, moving=False)` 및 update/frame_index 계약 유지
- 대표 방향은 규격 순서대로 front_right=-pi/4, back_right=pi/4, back_left=3pi/4, front_left=-3pi/4
- 최초 선택은 최근접 대표각, 동률 거리 오차 1e-12 rad 이내는 표 순서 우선. 이후 현재 대표각에서 45+5도 범위는 유지하며 각도 wrap 처리
- 최초 유효 update는 기본 front_right에 hysteresis를 적용하지 않음. 예: +2도 첫 갱신은 back_right, 그 다음 -2도 갱신은 back_right 유지
- 실제 변위 hypot(dx,dy)가 1e-6px를 넘을 때만 보행, 거리/32로 위상 순환. 움직임 방향은 facing 선택에 사용하지 않음
- 정지·벽에 막힌 변위 0·조준 방향 변경은 위상을 리셋하지 않음. 정지 프레임은 0, 이동 중 phase<0.5는 1, 그 외는 2
- 무효 각도·변위와 hypot이 무한대인 입력은 방향·위상·초기화 상태를 보존하고 moving=False로 처리
- 큰 유한 거리는 32px 나머지를 먼저 구한 뒤 위상에 더해 기존 소수 위상을 보존
- 분할 거리 누적이 0.5/1.0 경계 직전의 부동소수점 잔차로 다른 프레임을 고르지 않도록, 위상 경계 0·0.5·1에서 1e-12 이내만 정규화
- UI는 실제 move_player 전후 변위를 전달하고, 위치를 강제로 바꾸는 smoke fixture를 보행 변위로 넘기지 않음. 상대 파일 변경 요청 없음

## 실행 명령과 실제 결과

저장소 루트의 기존 .venv Python으로 실행

```powershell
& '.\.venv\Scripts\python.exe' -B -m unittest discover -s game/tests -p 'test_locomotion*.py' -v
```

실제 결과: `Ran 15 tests in 0.004s`, `OK`, 종료 코드 0

확인 범위: 최근접 대표각·초기 +2도·동률 허용오차·네 방향의 50도 경계·각도 wrap·32px 주기·유클리드 변위·거리 분할/FPS 독립·후진/옆걸음의 조준 독립·정지/방향 전환의 위상 보존·실제 core 벽 정지 변위·1e-6 경계·무효 입력 후 최초 유효 선택·큰 유한 거리와 hypot overflow

```powershell
& '.\.venv\Scripts\python.exe' -B -W error::SyntaxWarning -c "from pathlib import Path; names=('game/locomotion.py','game/tests/test_locomotion.py'); [compile(Path(name).read_text(encoding='utf-8'),name,'exec') for name in names]; print('syntax OK: 2 files')"
```

실제 결과: `syntax OK: 2 files`, 종료 코드 0

위 결과는 콘솔 판정 검사이며 창·GUI·네이티브 입력·스피커·에셋 외형 검사가 아님. 전체 UI 통합 검사는 지휘에게 인계

## 알려진 범위와 다음 상태

- 1e-6px 이하 변위는 정지로 취급하며 위상을 누적하지 않는 규격
- 방향을 바꾸거나 정지했다고 새 Locomotion을 만들지 않아야 기존 위상이 유지됨
- 공개 상태는 정상 초기값과 이 모듈의 갱신 경로를 전제. 외부에서 phase를 NaN 등으로 직접 덮어쓰는 사용은 이번 계약에 없음
- 독립 읽기 검토에서 추가 중대 오류 없음. 기존 core·속도·반경·벽·화면 변환을 수정하지 않음
- 전투·좀비·소음·손전등·배달·8방향·R2는 미착수

지휘 검수·수정·중간 커밋 후 사용자 2차 확인에서 정지. 사용자 확인과 다음 진행 요청 전 R2 착수 금지
