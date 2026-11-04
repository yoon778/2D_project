# 1주차 R1-B-S2 로직 집중 검사 인계

기준일: 2026-11-05 · baseline 358978f
상태: 자체 집중 검사 완료, 지휘 검수 요청 후 정지
기준: [나머지 3방향 보행 개선 규격](../r1b-smooth-s2-contract.md)

## 변경 파일

- [game/tests/test_locomotion_s2.py](../../game/tests/test_locomotion_s2.py): 실제 core 변위와 4방향·8장 보행의 조합 검사 5개
- 이 보고서

기존 테스트 21개와 game/locomotion.py·core.py는 수정하지 않음. baseline 대비 두 실제 로직 파일의 diff 없음 확인
main·player_visual·에셋·공용 문서·Git도 변경하지 않음

## 집중 확인 결과

1. 네 조준 방향 각각 전진·후진·옆걸음의 실제 core 이동을 8/24/60회로 분할. 0.4초 동안 총 36px, phase=0.125·8장 frame2와 조준 방향 유지
2. 네 방향으로 전환하며 정지·재출발. 방향 변경 시 기존 phase 보존, 정지는 frame0, 실제 추가 거리만 기존 phase에 누적
3. 벽 네 면에 0.05초 갱신으로 접근. 실제 16px 접촉 이동은 phase=0.5·frame5, 계속 미는 입력은 변위0·idle0, 4.5px 후퇴 재개는 phase=0.640625·frame6
4. 벽 네 면에서 비스듬한 슬라이딩. 요청 속도에 해당하는 4.5px 대신 실제 접선 이동 약 3.181980515px만 위상에 반영, frame1 유지. 요청 거리로 계산하면 frame2가 되어 구분 가능한 검사
5. 네 방향의 대표각+50도 유지·초과 시 전환, 각도 wrap, 28→32px의 frame8→1, 정지 frame0·재출발 4px frame2 확인

재현된 순수 로직 오류가 없어 구현 변경과 새 시스템 추가는 하지 않음

## 실행 명령과 실제 결과

저장소 루트의 기존 .venv Python으로 실행

```powershell
& '.\.venv\Scripts\python.exe' -B -m unittest discover -s game/tests -p 'test_locomotion*.py' -v
```

실제 결과: `Ran 26 tests in 0.010s`, `OK`, 종료 코드 0
기존 21개와 신규 5개 모두 통과

```powershell
& '.\.venv\Scripts\python.exe' -B -W error::SyntaxWarning -c "from pathlib import Path; name='game/tests/test_locomotion_s2.py'; compile(Path(name).read_text(encoding='utf-8'),name,'exec'); print('syntax OK: test_locomotion_s2.py')"
```

실제 결과: `syntax OK: test_locomotion_s2.py`, 종료 코드 0

```powershell
git diff 358978f --name-only -- game/core.py game/locomotion.py
git diff --stat -- game/tests/test_locomotion.py
```

실제 결과: 두 명령 모두 출력 없음, 종료 코드 0. 실제 로직·기존 검사 변경 없음

## 검증 범위와 한계

- 공개 Locomotion와 실제 core 이동 함수의 조합을 검사한 결과이며 실제 main 루프·새 이미지 연결·메타의 36자세 존재 검사와 구분
- 신규 5개는 방향별 대표 상태 조합 검사. 8장 구간의 경계 검사는 기존 21개에 포함되며, 새 에셋의 4방향×8장 전체 순회 시각 검사는 아님
- 네이티브 창·GUI·자동 입력·SDL 렌더·출력 장치 청취를 실행하지 않음
- 새 방향의 외형·양발 교대·장비 손·고정 크기/root·실제 연속 보행 체감은 지휘·UI·사용자 검수 대상
- 사용자 물리 키보드 검수 완료로 기록하지 않음. 상대 파일 변경 요청 없음

다음 상태: 지휘 방향별 검수·수정·중간 커밋과 최종 사용자 2차 확인 대기. R2 미착수
