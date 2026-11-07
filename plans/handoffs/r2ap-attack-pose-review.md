# R2-AP 공격 자세 검수 · 11/7 1주차

[규격](../r2ap-attack-pose-contract.md) · 기준 `ed4d20a` · 에셋 `b5ff386`

- 앞오른쪽 시안에서 주인공은 어깨와 몸통이 방망이를 따라가고 타격 때 방망이 끝이 상자보다 앞으로 나옴. 좀비는 웅크린 뒤 가슴과 양손이 함께 나가며 회수 자세의 손 픽셀 분리도 보정함.
- 정지 12장, 이동 12×8장, 좀비 12장을 검사함. 끝 자세·피벗·다른 일곱 방향 보존, 좀비 alpha 마스크·재현·팔 연결 확인. `node art/r2ap-check.cjs`.
- Windows SDL 숨김 창에서 주인공 정지·이동 공격과 좀비 공격을 재생함. 전후 각 36자세 확인 및 이동·피해 추적 일치. 로직 채팅에서 0.18초·0.30초 타격과 공격 종료, R2-ZT 방향 유지·복귀 재확인. 전체 164개 통과.
- `output/review/R2-AP/`의 `player-before-after.gif`, `player-walking-before-after.gif`, `zombie-before-after.gif`는 좌 기존·우 수정. 실제 조작 체감과 일곱 방향 확대는 앞오른쪽 사용자 확인 뒤 결정.
