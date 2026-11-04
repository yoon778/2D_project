# 1주차 R1-B-S1 로직 인계

기준일: 2026-11-05
상태: 자체 집중 검사 완료, 지휘 검수 요청 후 정지
기준: [한 방향 보행 개선 규격](../r1b-smooth-contract.md)

## 변경 파일과 구현

- [game/locomotion.py](../../game/locomotion.py): `Locomotion.walk_frame_index(frame_count: int) -> int` 조회 메서드만 추가
- [game/tests/test_locomotion.py](../../game/tests/test_locomotion.py): 기존 15개 유지, 새 메서드 검사 6개 추가
- 이 보고서

정지는 0, 이동은 phase 구간에 따라 1..N 반환. 8장일 때 4 지면 px마다 프레임이 바뀌며 전체 주기는 기존 32px
양의 정수 아닌 값은 idle 상태에서도 ValueError. bool·0·음수·float·문자열·None·NaN·무한대 거부
2장 조회는 기존 frame_index를 그대로 반환하여 기존 경계 선택과 호환
분할 거리 누적의 부동소수점 오차는 내부 구간 경계의 조회 계산에서만 1e-12 위상 단위 이내로 보정. 저장된 phase·facing·moving과 최초 초기화 상태는 변경하지 않음
유효 phase가 1 직전이면 마지막 프레임 N을 유지하며, 실제 update에서 phase가 0으로 순환한 경우 프레임 1 반환

기존 update·frame_index·방향 선택·이동 90px/s·32px 주기·core·SDL·이미지·UI 파일은 변경하지 않음
UI는 현재 방향의 보행 장수 `len(frames)-1`을 새 메서드에 전달하면 됨. 추가 상대 파일 변경 요청 없음

## 실행 명령과 실제 결과

저장소 루트의 기존 .venv Python으로 실행

```powershell
& '.\.venv\Scripts\python.exe' -B -m unittest discover -s game/tests -p 'test_locomotion*.py' -v
```

실제 결과: `Ran 21 tests in 0.006s`, `OK`, 종료 코드 0
기존 15개 회귀와 신규 6개 모두 통과

신규 검사: idle·2/8장 선택, 정확 경계/앞뒤 구간/마지막 구간, 2장 legacy 호환, 잘못된 장수의 ValueError, 반복 조회의 상태 불변, 4~48px를 1/10/30/60/100/144회로 나눈 8장 선택의 FPS 독립
4px를 10회로 나눌 때 이전 프레임이 남는 오류를 먼저 재현한 후, 위상 갱신을 바꾸지 않고 조회 계산만 보완

```powershell
& '.\.venv\Scripts\python.exe' -B -W error::SyntaxWarning -c "from pathlib import Path; names=('game/locomotion.py','game/tests/test_locomotion.py'); [compile(Path(name).read_text(encoding='utf-8'),name,'exec') for name in names]; print('syntax OK: 2 files')"
```

실제 결과: `syntax OK: 2 files`, 종료 코드 0
독립 읽기 검토에서 추가 중대 계약 오류 없음

## 한계와 다음 상태

- 이 검사는 프레임 선택과 기존 로직 회귀의 확인이며, 새 8자세 이미지의 외형·접지·실제 부드러움을 입증하지 않음
- 실제 상태는 기존 계약대로 phase=[0,1)을 전제. 이미지·UI 연결·다른 세 방향의 렌더 회귀는 지휘와 UI 담당 검수 대상
- 네이티브 창·GUI·자동 입력·게임 실행·Git 조작 없음
- 지휘 검수·수정·중간 커밋 후 사용자 2차 확인에서 정지, R2 미착수
