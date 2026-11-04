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
