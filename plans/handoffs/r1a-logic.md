# R1-A 로직 인계

기준일: 2026-11-04
상태: 로직 자체 확인 완료, 지휘 1차 검수 요청 후 정지
기준: [지휘 절차 6절](../commander-runbook.md)

## 변경 파일

- [game/core.py](../../game/core.py): 순수 Python 지면 상태·이동·충돌·조준
- [game/tests/test_core.py](../../game/tests/test_core.py): 공개 API의 판정 테스트 16개
- 이 보고서

담당 밖 파일과 Git 인덱스·브랜치는 변경하지 않음

## 구현 결과와 UI 연결

- `Player`, `Wall`, 상수 4개와 `move_player`·`aim_player`의 시그니처·기본값은 지휘 절차 6절과 동일
- `Player()`는 발점 (480,180), 조준 pi/4, moved=False. 월드 960×720, 속도 90px/s, 반경 14px
- 벽은 UI가 `Wall(400,330,220,60)`로 전달. core에 화면 좌표·투영·SDL 의존성 없음
- 비영 입력 벡터를 정규화하고 원과 벽 직사각형의 축별 접촉점까지 이동. 작은 단계로 나눠 모서리·벽 슬라이딩과 긴 갱신의 벽 통과 방지
- 월드 내 발점 범위는 x=14~946, y=14~706. 벽 네 면에서 반경 14를 유지하며 접선 이동·후퇴 가능
- `moved`는 이번 호출 전체의 실제 변위 여부. 벽 앞 제자리·무입력·무효 dt에서는 False
- 이동은 조준각을 바꾸지 않음. 조준은 지면 +x 기준 반시계 연속 rad이며 위치·moved를 바꾸지 않고 같은 점에서는 기존 각도 유지
- UI는 화면→지면 역변환한 목표를 `aim_player`에 전달하고 프레임 dt<=0.05를 유지

## 실행 명령과 실제 결과

아래 명령은 저장소 루트의 기존 .venv Python으로 실행함

```powershell
& '.\.venv\Scripts\python.exe' -B -m unittest discover -s game/tests -p 'test_core*.py' -v
```

실제 결과: `Ran 16 tests in 0.077s`, `OK`, 종료 코드 0

확인 범위: 8방향 90px/s·대각선 정규화·0.05초 갱신 누적·벽 네 면 접근/슬라이딩/후퇴·월드 네 변과 모서리·접선·원형 모서리 접촉·큰 dt·무입력·moved·연속 조준·같은 점 조준·이동과 조준 독립

```powershell
& '.\.venv\Scripts\python.exe' -B -W error::SyntaxWarning -c "from pathlib import Path; names=('game/core.py','game/tests/test_core.py'); [compile(Path(name).read_text(encoding='utf-8'),name,'exec') for name in names]; print('syntax OK: 2 files')"
```

실제 결과: `syntax OK: 2 files`, 종료 코드 0

위 결과가 이 보고서의 콘솔 검증 증거이며 별도 렌더 이미지·오디오 증거는 생성하지 않음
실제 창·키보드 조작감·사선 표시·출력 장치 청취는 이 로직 자체 검사에서 확인하지 않음

## 안전 처리와 한계

- dt<=0, NaN·무한대·숫자가 아닌 dt는 이동 없이 무시하고 moved=False로 처리
- 매우 큰 유한 dt와 극소 축 조합의 과도한 반복을 방지하기 위해 한 호출은 최대 10초만 처리. dt>10의 전체 경과 시간을 보존하는 시뮬레이션은 아님
- `(1,1e-8), dt=1e308` 입력은 별도 프로세스의 3초 제한 회귀 테스트로 종료 확인. 실제 UI의 최대 0.05초 입력에는 위 상한의 영향 없음
- 유효한 월드 내·벽과 겹치지 않는 시작 위치, 양의 크기의 고정 벽을 전제. 잘못된 배치의 자동 밀어내기는 이번 범위에 없음
- 축별 충돌은 X축 우선. 모서리의 실제 조작감·화면 가림은 UI 연결 후 지휘가 확인 필요
- 추가 상대 파일 변경 요청 없음. 전투·좀비·소음·스태미나·손전등·배달·R1-B는 구현하지 않음

다음 상태: 지휘 1차 검수·수정 요청 대기. 사용자 2차 확인과 다음 지시 전 추가 묶음 착수 금지

## 2026-11-04 재개 분석: 네이티브 자동 입력 미반응

사용자 재개 요청 후 지휘의 읽기 분석 배정으로 수행. 게임 창·SDL·Windows 입력은 실행하지 않았고 core·UI 소스·Git은 변경하지 않음
새 구현이나 지휘 1차 통과를 뜻하지 않으며, 분석 인계 후 후속 배정 대기

### 코드에서 확인한 사실

- [main.py](../../game/main.py)의 이벤트 루프는 KEYDOWN에서 pressed에 추가하고 KEYUP에서 제거한 뒤, 배치 전체 처리가 끝나면 축을 계산해 이동을 한 번 호출
- 따라서 같은 프레임의 DOWN→UP는 이동 전에 상쇄됨. 짧은 탭을 놓칠 수 있는 상태 샘플 방식이며, 이것만으로 지속 입력이나 core 이동 오류를 뜻하지 않음
- 설치된 `.venv/Lib/site-packages/pico2d/pico2d.py:213~238`은 SDL_PollEvent를 한 번의 호출에서 끝까지 비우며, 키 이벤트의 repeat가 0일 때만 keysym.sym을 반환
- pico2d는 windowID·scancode·repeat·창 포커스 이벤트를 반환 목록에 보존하지 않음. 현재 지휘 observer처럼 p.get_events 반환만 기록하면 원시 이벤트 없음과 필터 제거를 구분할 수 없음
- SDL keysym은 w=119, d=100. Windows VK 87/68 또는 scancode 26/7을 keysym.sym 대신 쓰면 서로 다른 값임
- 이벤트 수신 후에도 focused=False이면 pressed를 지우고 dt=0으로 이동을 호출. 포커스 상태는 이벤트 수신과 같은 프레임에 기록해야 함
- `--smoke-test`는 매 프레임 위치를 fixture로 덮어쓰므로 입력 검수용 실행이 아님. 지휘 observer는 인수 없는 main.run()을 호출하므로 해당 분기는 그 observer의 원인이 아님

### 창 없는 코드 재현: 실제 관측 결과

main.py의 키 이벤트 for 문을 AST로 읽어 메모리에서 실행하고, 순수 core의 move_player에 dt=0.05·시작 벽을 전달. main·pico2d 모듈과 SDL 창을 실행한 검사는 아님

| 전달한 변환 후 이벤트 | 최종 발점 | 뜻 |
| --- | --- | --- |
| 같은 프레임 D DOWN→UP | (480,180) | pressed가 이동 전에 비워짐 |
| 프레임을 나눈 D DOWN / UP | (484.5,180) | 한 프레임 4.5px 이동 |
| 프레임을 나눈 W DOWN / UP | (480,184.5) | 한 프레임 4.5px 이동 |
| 키 이벤트 없음 | (480,180) | 좌표만으로는 짧은 탭과 구분 불가 |

실행 명령은 다음 here-string을 기존 .venv Python의 stdin으로 전달했으며 종료 코드 0

```powershell
@'
import ast
import json
from pathlib import Path
from types import SimpleNamespace as NS
from game.core import Player, Wall, move_player
source = ast.parse(Path('game/main.py').read_text(encoding='utf-8'))
loop = next(n for n in ast.walk(source) if isinstance(n, ast.For)
            and isinstance(n.iter, ast.Call) and isinstance(n.iter.func, ast.Attribute)
            and n.iter.func.attr == 'get_events')
handler = compile(ast.Module(body=[loop], type_ignores=[]), 'game/main.py:event-loop', 'exec')
p = NS(SDL_QUIT=256, SDL_KEYDOWN=768, SDL_KEYUP=769, SDLK_ESCAPE=27)
down = lambda key: NS(type=768, key=key)
up = lambda key: NS(type=769, key=key)
for name, batches in (
    ('same_frame_D', ([down(100), up(100)],)),
    ('separate_frames_D', ([down(100)], [up(100)])),
    ('separate_frames_W', ([down(119)], [up(119)])),
    ('no_events', ([],)),
):
    player = Player()
    context = {'p': p, 'pressed': set(), 'running': True}
    for batch in batches:
        p.get_events = lambda batch=batch: batch
        exec(handler, context)
        keys = context['pressed']
        move_player(player, int(100 in keys)-int(97 in keys),
                    int(119 in keys)-int(115 in keys), 0.05, (Wall(400,330,220,60),))
    print(json.dumps({'case': name, 'position': [player.x, player.y],
                      'pressed': sorted(context['pressed'])}))
'@ | & '.\.venv\Scripts\python.exe' -B -
```

### 지휘 증거와 다음 최소 검사 제안

지휘 전달 증거: 실제 Windows SDL observer에서 CUA pressKey('w') 후 반환 키 이벤트 0개·좌표 불변. 같은 배치 DOWN→UP라면 반환 로그에는 두 이벤트가 있어야 하므로, 이 관측을 짧은 탭 상쇄로 확정하면 안 됨
합성 키의 SDL 미도달이 유력한 가설이나 원시 PollEvent·repeat 필터·포커스를 확인하기 전에는 원인 확정 불가

지휘가 기존 observer의 실제 SDL_PollEvent 반환 직후를 감싸 다음 정보를 추가 기록하는 방법을 제안. 로그를 위해 두 번째 PollEvent를 호출하거나 이벤트를 별도로 소비하지 않음

- 원시 키: 프레임·순서·timestamp·type·windowID·repeat·keysym.sym·scancode
- 같은 프레임: 게임 창 ID·SDL 키보드 포커스 창 ID·INPUT_FOCUS 플래그
- 변환 후: p.get_events 이벤트 목록, 이동 직전 pressed·축·dt, 이동 전후 좌표·moved
- 원시 창 포커스 이벤트와 TEXTINPUT도 확인하면 포커스 전환·텍스트 전송을 키 입력과 구분 가능
- 이벤트가 없어도 주기적으로 프레임·포커스·좌표를 기록해 폴링이 진행 중인지 확인

지휘 실행 명령 제안: `.\.venv\Scripts\python.exe -B output/review/R1-A/observe_native_input.py` — 이 분석 담당은 해당 명령을 실행하지 않음

| 추가 추적 결과 | 판별 |
| --- | --- |
| 원시 키 없음 | 합성 입력 전달·대상 창·포커스 경로 조사 |
| 원시 키 있음, pico2d 반환 없음 | repeat 필터·이벤트 유형 확인 |
| 반환 DOWN/UP가 같은 프레임, 축 0 | 짧은 탭 상쇄 경로 |
| 반환 DOWN 있음, focused=False | 포커스 정책에 따른 입력 초기화 |
| 올바른 축·양의 dt·focused=True인데 초기 위치 불변 | 이후 core 호출/위치 덮어쓰기 경로 조사 |

실제 Windows 키 전달·지속 입력·물리 키보드 검증은 지휘의 별도 확인 대상. 사용자 2차 확인은 아직 없음
