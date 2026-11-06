# R2-AW 이동 공격 하체 연결 · 2026-11-06

사용자 승인: 이동 공격 중 발 고정 해소·두 채팅 지시·게임 적용·검수·중간 커밋
기준선 `8463c04`, 실제1주차. 앞·오른쪽 한 방향 안의 보완이며 타 방향 공격/R3는 포함하지 않음

## 소유권

- UI·에셋: `art/player/r2a-combat-assets.cjs`, `game/combat_visual.py`, `game/main.py`, 별도 이동 공격 PNG/기존 전투 메타, 관련 visual 검사
- R1 제작 도구 `art/player/consistent-walk.cjs`는 기존 `drawLeg`/`joints` export와 require.main 실행 가드만 허용. 알고리즘·R1 원화/부품/72자세 PNG/메타·core/locomotion/player_visual·전투 로직은 불변
- 로직: 새 `game/tests/test_attack_walk_logic.py`에 공개 CombatWorld/Locomotion의 이동·정지·벽·공격 경계/위상 검사. 생산 로직 수정 없이 결과 보고
- 지휘: 통합/실제 렌더·시간 측정·문서·Git. 담당 밖 변경·Git은 금지

## 연결 규격

- 기존 정지 공격6장·좀비 PNG·0.6초/0.18초 판정·90/60px/s·stride64 유지
- 공격6단계×보행8위상의48개 전신 변형을 오프라인 베이크. 같은 한 방향이며 기준몸64·96셀·피벗(48,80)·2배 nearest 유지
- 새 `attack_walk` 메타: PNG768×576(8열6행), frames48. 인덱스=공격단계0..5×8+걷기프레임1..8−1, 기존 attack/zombie 메타 블록 보존
- `CombatVisual.draw_attack(attack, foot_x, foot_y, walk_frame_index=None)`: 1..8은 이동 변형, 0/None은 기존 정지 공격
- Renderer는 현재 `player_visual.frame_index`를 전달. 시간은 world.attack.elapsed, 보행은 기존 Locomotion의 실제 이동 거리만 사용. 새 보행 타이머/공격 시작 시 위상 초기화 금지
- 원래 방망이가 가렸던 다리는 승인 부품과 기존 drawLeg/joints로 복원해 사용. 최종 R1 PNG에서 무기만 지워 다리에 빈 구멍을 만들지 않음
- 상체/팔/손/방망이는 같은 보행1px bob으로 연결, 다리에는 bob 이중 적용 금지. 택배·그립·원화 신체 비율·윤곽·깊이 순서 보존
- 마지막 복귀 단계의8변형은 기존 FR 보행 PNG를(8,8) 옮긴 것과 RGBA 일치. 공격 종료 후 같은 보행 위상으로 연결
- 멈춤/벽에 막힘은 정지 공격 선택·위상 유지, 재출발은 그 위상에서 진행. 서서 공격은 기존6장 유지
- 프레임 중 파일/이미지 생성·로드 금지, 이동 공격 텍스처도 초기화에 한 번 로드

## 검수

1. 전진/후진/옆걸음의 단계·위상, 시작·종료·정지/재출발·벽·포커스·R 검증
2. 48셀 잘림/팔레트/복귀8장 실제RGBA·원화/기존 에셋 보존 확인
3. 실제 Windows 이동 공격 연속 캡처·발 교대·무기/몸 가림·공격 종료 연결 검수
4. 표시창 프레임 시간·재시작/해제 확인, 합성 입력과 사용자 실제 조작감 구분
5. 지휘 수정/커밋 후 사용자2차 확인에서 정지
