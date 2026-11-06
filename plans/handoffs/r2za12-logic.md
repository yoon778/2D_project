# R2-ZA12 검사 인계 · 실제 1주차

기준선 `2e954a6`. 메타 기반 동적 runtime/판정/HUD를 보존했으며 실제12자세 에셋 인계 후 영향20개 검사 통과·담당 파일 동결을 완료했다.

- 변경은 `game/tests/test_zombie_visual_r2z.py`, `game/tests/test_zombie_attack_visual_r2za.py`와 이 인계 문서다. 에셋·생산 코드·Git은 변경하지 않았다.
- 메모리 공격 fixture를640×960/방향당12자세로 갱신했다. 경계0/.04/.08/.12/.16/.23/.30/.40/.46/.52/.64/.72/.80에서 현재 프레임·각 구간 종료 직전 선택·96자세 발점/소스별alpha 픽킹을 검사한다.
- 실제 JSON의8방향/12경계/캔버스/셀clip/절대피벗을 확인하는 검사1개를 추가했다. 기존8자세 소스에서는640×640≠640×960 실패를 확인했다.
- 실제 SDL queue 기대값도12시각 단계로 갱신했다. 기존 .30초 단일 피해/.80초 회복·취소·회피·포커스/R·위상·47초기로드/추가로드0/해제 검사를 유지한다.

## 최종 검증

- 판정7개(1/240/불규칙dt 포함)+기존 좀비 순수 상태4개+새12자세 시각fixture2개, 총13개 통과했다. 제품 스텁은 생성하지 않았다.
- 실제 에셋 인계 후 `.venv/Scripts/python.exe -B -m unittest game.tests.test_zombie_attack_logic_r2za game.tests.test_zombie_visual_r2z game.tests.test_zombie_attack_visual_r2za`의20개를1회 실행했다.
- 결과: `Ran 20 tests in 3.237s`, `OK`, 종료코드0. 실제 SDL queue는 새12자세 PNG/JSON을 사용했고 대체 텍스처/메타 fixture는 적용하지 않았다.96상태 소스/픽킹 단위 검사는 별도 메모리 fixture/mock draw를 사용한다.
- 실제12메타의 경계/clip/피벗과 SDL queue의12시각 단계·.30 단일 피해/.80 회복·취소/회피/포커스/R·보행 복귀·47초기로드/추가로드0/해제 검사를 통과했다. 입력 검사는 기존 SDL dummy/software·고정dt·포커스 surrogate를 사용했다.
- 판정의1/240/불규칙dt 회귀도 통과했다. 검사 후 생산 코드·판정·HUD·에셋·Git 추가 변경은 없었다.
- 로그는 `output/review/R2-ZA12-logic/actual-source-tests.txt`, 검사 직후 소스 해시는 같은 폴더의 `actual-source-snapshot.json`에 저장했다. 최종 아트 동결/품질은 지휘 확인 범위다.
- 전체 회귀·기존64키/8idle복귀 RGBA·실제 Windows96상태/8실공격/회피/취소/추격복귀·표시창 성능/자원·사용자 체감은 지휘 검수 범위다.
