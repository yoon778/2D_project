# R2-FR12 로직 검사 인계 · 실제 1주차

기준선 `9f33924`. FR12 실제 PNG/메타 인계 후 영향31개 검사(기존30개+새 회귀1개)를 통과했으며 담당 파일을 동결했다.

- `CombatVisual`/main은 기존 메타 기반 동적 동작으로12단계를 지원하므로 생산 코드를 수정하지 않았다. core/locomotion/player_visual/combat.py·에셋·JS·Git도 변경하지 않았다.
- 담당 변경은 `game/tests/test_combat_visual_r2a.py`, `game/tests/test_attack_walk_visual.py`, `game/tests/test_combat_directions_r2c8.py`와 이 인계 문서다.
- FR 경계0/.045/.09/.135/.18/.225/.27/.32/.37/.425/.48/.54/.6의 정확한 시작·종료 직전 선택을 검사한다. 실제 CombatWorld로 .18 단일 피해·0.4초 경직·.6 회복 잠금을 확인하는 회귀1개를 추가했다.
- 정지384×288/4열3행·이동768×1152/8열12행,12×8개 이동 인덱스와96셀/피벗/2배 표시를 확인한다. 나머지7방향은 기존6단계/48이동 셀 기대값을 유지한다.
- 기존 실제 SDL queue 회귀를 재사용하며 FR 이동 공격에서12시각 단계 모두가 나타나는지 확인한다. 정지·벽·재출발·종료 위상·포커스/R·누름 반복/해제 검사를 유지한다.

## 최종 검증

- 실제 에셋 인계 후 `.venv/Scripts/python.exe -B -m unittest game.tests.test_combat_visual_r2a game.tests.test_attack_walk_visual game.tests.test_combat_directions_r2c8`를1회 실행했다.
- 결과: `Ran 31 tests in 14.116s`, `OK`, 종료코드0. 기존30개+새 단일 타격/12단계 회귀1개를 포함한다. SDL queue 실행에 방향/캔버스/PNG 대체 fixture를 적용하지 않았다.
- FR12의 모든 경계·정지12/이동96셀·새 캔버스/피벗, 다른7방향6/48셀,17소스 초기 로드·오류 정리와 기존 실제 앱 루프/SDL queue 회귀를 확인했다.
- 입력 회귀는 SDL dummy/software·고정dt·포커스 surrogate를 사용했다. 12시각 단계 모두 표시, 실제 이동 거리의 위상, 정지/벽/재출발/공격 종료, 저장 각도/방향, 포커스/R, 누름 반복/해제와 종료 정리 경로를 통과했다.
- 생산 코드 추가 수정·에셋 변경·Git 작업은 없었다. 초기 메모리 FR12 메타 fixture 검사 외에 제품 스텁도 생성하지 않았다.
- 전체 검사·실제 Windows108상태·복귀9화면 RGBA·표시창 성능·사용자 모션 체감은 지휘 검수 범위다. 다른7방향의 중간 자세 확장은 포함하지 않는다.
