# 1주차 R1-B 4방향·짧은 보행 연결 규격

기준일: 2026-11-04
사용자 `그러면 계속 개발 진행해보자` 요청을 R1-B 착수 허용으로 기록함
R1-A 실제 물리 키보드를 확인했다는 별도 결과는 받지 않았으므로 검수 완료로 만들지 않음
이번 묶음은 R1-B 하나이며 지휘 검수·수정·중간 커밋 후 사용자 2차 확인에서 정지함

## 목표와 소유권

기존 사선 장면·지면 이동·벽·연속 조준을 유지하며 캐릭터의 4방향 자세와 2프레임 보행을 연결함
새 좀비·전투·손전등 마스크·배달·맵 아트·8방향은 이번 범위에 넣지 않음

| 담당 | 변경 파일 |
| --- | --- |
| 로직 채팅 | game/locomotion.py, game/tests/test_locomotion*.py, plans/handoffs/r1b-logic.md |
| UI·에셋 채팅 | game/player_visual.py, game/main.py, game/assets/player/r1b-*, game/tests/test_visual*.py, plans/handoffs/r1b-ui.md |
| 지휘 | 연결 규격·진행 문서·독립 검수·수정 요청·Git |

core.py·지면 속도 90px/s·충돌 반경 14·벽 배치·화면 변환은 변경하지 않음
담당 밖 파일 변경이 필요하면 지휘에게 먼저 보고함
Git 조작과 공용 문서 변경은 지휘만 수행함

## 4방향과 조준

몸의 대표 자세를 지면 조준각으로 선택함. 이동 방향으로 몸을 돌리지 않음
연속 조준각과 마우스 표식은 양자화하지 않음

| ID | 대표 지면 각도 | 화면에서 보는 자세 |
| --- | --- | --- |
| front_right | -pi/4 | 앞·오른쪽, 얼굴·가슴 일부 보임 |
| back_right | pi/4 | 뒤·오른쪽, 가방이 보임 |
| back_left | 3*pi/4 | 뒤·왼쪽, 가방이 보임 |
| front_left | -3*pi/4 | 앞·왼쪽, 얼굴·가슴 일부 보임 |

초기 선택은 가장 가까운 대표 각도, 동률은 위 표 순서 우선
동률 비교의 부동소수점 오차는 1e-12 rad 이내를 같은 거리로 봄
이전 방향이 있으면 대표 각도로부터 45도+5도 이내에서는 유지함
경계를 충분히 넘었을 때만 바꿔 작은 마우스 흔들림으로 방향이 반복 전환되지 않게 함
전체 PNG 회전·좌우 반전으로 다른 방향을 대신하지 않음
왼손 몸 앞 택배·오른손 방망이·가슴 부착등은 모든 방향에서 유지함

## 로직의 순수 API

```python
STRIDE_DISTANCE = 32.0  # 지면 px, 한 보행 주기

def select_facing(aim_angle: float, current: str | None = None) -> str: ...

@dataclass
class Locomotion:
    facing: str = "front_right"
    phase: float = 0.0
    moving: bool = False

    def update(self, aim_angle: float, dx: float, dy: float) -> None: ...

    @property
    def frame_index(self) -> int: ...
```

phase는 [0,1), 실제 변위 hypot(dx,dy)/32를 더해 순환함
최초 유효 update는 기본 facing에 여유 각도를 적용하지 않고 select_facing(aim_angle, None)으로 선택함. 이후 유효 갱신부터 이전 방향을 사용하며 초기화 여부는 내부 상태로 관리함
실제 변위가 1e-6 지면 px 이하이면 moving=False, 그 외 True
frame_index는 정지 0, 이동 중 phase<0.5이면 1, 그 외 2
정지·방향 전환 시 phase는 보존하되 정지 화면은 idle 0을 사용함
뒤로·옆으로 움직여도 facing은 조준 방향을 유지하고 실제 변위만 보행 위상을 진행함
core·SDL·화면·이미지 파일에 의존하지 않는 작은 순수 모듈로 작성함
잘못된 조준각·변위는 안전하게 기존 방향/위상을 유지하고 이동 보행을 재생하지 않음

## UI 연결

```python
PlayerVisual.update(aim_angle: float, dx: float, dy: float) -> None
PlayerVisual.draw(foot_x: float, foot_y: float) -> None
```

main은 move_player 전후의 실제 좌표 차이를 구하고 aim_player 뒤 update를 호출한 뒤 기존 draw를 사용함
벽 앞 정지·포커스 상실·무입력 때 변위 0이면 보행하지 않음
smoke fixture의 위치 강제 배치는 실제 이동으로 넘기지 않음
창 제목은 `Dead Route - R1-B`, 화면 안내도 4방향·보행 단계에 맞게 변경함
마우스 y 변환·raw SDL 이벤트·포커스 초기화·Esc/QUIT·리소스 정리는 유지함
기존 테스트의 제목 기대값은 새 단계 계약에 맞게 갱신하고 기존 검증 범위는 유지함

## 에셋과 메타데이터

기존 도트풍 PNG를 정체성·시점·장비의 참조로 사용해 내장 imagegen으로 12자세 투명 atlas를 제작함
권장 배치: 3열(idle/왼발 보행/오른발 보행) × 4행(위 표의 4방향), 격자선·문자·그림자·바닥 없음
먼저 한 번 생성·검수하고 실제 오류가 있을 때만 지휘를 통해 수정함
그림을 프로그램으로 다시 그리거나 전체 반전·회전하지 않음. alpha 분석과 게임의 runtime clip은 허용됨

파일: game/assets/player/r1b-courier-atlas-20261104.png, 같은 이름의 .json·.prompt.txt
기존 R1-A PNG·메타·프롬프트는 사용자가 확인한 그림체의 참조로 유지하고 새 메타에서 용도를 연결함
메타는 실제 canvas_size·출처·정확한 입력·SHA256·각 셀의 clip/발점·표시 배율·검수 한계를 기록함
실제 출력이 64px 원본 또는 정확한 고정 픽셀 격자라고 가정하지 않음

새 메타의 기본 호환 필드 image/canvas_size/clip_topleft/foot_pivot_topleft/display_height/sampling은 front_right idle을 뜻함
display_height=128, sampling=nearest. frames[direction]에 idle·walk1·walk2 순서로 clip_topleft와 foot_pivot_topleft를 기록함
같은 방향의 모든 프레임은 그 방향 idle의 source 높이를 기준으로 같은 배율을 사용함
매 프레임마다 bbox 높이를 128로 억지 정규화하지 않아 몸 크기가 펌핑하지 않게 함
각 방향 idle의 표시 높이는 128px를 기준으로 맞추고 프레임 간 접지점·head 크기·장비 손을 검토함
PlayerVisual의 METADATA_PATH는 새 atlas JSON을 가리킴. 기존 sprite_rect 함수와 draw 호출 형태는 유지함

## 완료 기준과 인계

- 로직: 대표 방향·동률·각도 wrap·5도 여유, 조준/이동 독립, 실제 거리 위상, 정지·벽·방향 전환의 위상 유지 검사
- UI: 12자세가 실제 파일에 있고 clip/발점이 셀 밖으로 나가지 않으며 nearest·공통 배율·방향/프레임 선택이 맞는지 검사
- 실제 앱 루프: 새 update가 실제 변위를 받고 포커스/벽 앞에서 idle인지, 마우스로 방향이 바뀌는지 검사
- 지휘: 12자세·대표 실제 렌더·발점·크기 흔들림·택배/방망이 손·기본 이동/가림을 확인하고 필요 시 수정 요청
- 사용자: 4방향 몸 방향·걷기/후진/옆걸음·발 모양·크기·실제 키보드를 2차 확인

각 담당은 실제 실행 명령·결과·증거·미확인 항목을 자기 보고서에 쓰고 정지함
자동 SDL 사건 재생·실제 Windows 렌더·CUA·사용자 물리 키보드 결과는 구분함
모든 중간 커밋은 `feat: 1주차 R1-B ...`, `fix: 1주차 R1-B ...`처럼 작성함
R1-B 사용자 2차 확인과 다음 진행 요청 전에는 R2를 배정하지 않음
