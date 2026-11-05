# R1-W2 UI·에셋 인계

기준일2026-11-05 · baseline05f55ed

## 착지 비교 시안 통합 완료

FRwalk8만 새 landing_front_right로 교체했다. 모든idle·다른3방향 전체 frames·기존7source사전/PNG/프롬프트와 엔진4파일을 정확히 보존했다. 최종4방향×9/총36자세·8소스다.90px/s·32px주기·균등8위상·입력/조준/충돌/hold는 변경하지 않았다. 기존 W1도 비교용 소스로 보존했다.

내장 image_gen.imagegen·transparent_background=true로 기존 W1을 직접 확인·참조해 최초1회와 표적교정2회를 진행했다. 최초 exec-ac2d0d26-2254-4279-922b-3b19c725d33c.png는 실제 무릎/골반 압축이 보였으나 cap범위20sourcepx로 과도했고 반주기 지지가 모호했다. 교정1 exec-0af2fb34-9943-42af-8440-27ed9d5d6c01.png도16sourcepx 범위와 모호한 교대가 남아 미채택했다. 지휘 지시로2/6압축을 매우 얕게 줄이고5/6의 방망이쪽 hip→knee→boot 선행 연결을 복원한 교정2를 채택했다. 지휘가 최신 원본을 검토한 뒤 통합을 허용했다. 추가 생성은 하지 않았다.

- 선택 원본 exec-e644eac9-237b-4f9b-bd69-03c54bd65ea8.png
- 파일 game/assets/player/r1-weight-landing-front-right-20261105.png와 정확한 최초/교정1/교정2 프롬프트 .prompt.txt
- 실제1774×887 RGBA, SHA256 27DCBFB0004DC06943CB15A7DC3F279167EE84002D6FF066235949DA7EE562D8
- 원본 픽셀 그대로 복사·프로그램 그림 이동/회전/반전/복제/크로스페이드 없음
-4×2 실제 경계 x=[0,443,887,1330,1774],y=[0,443,887]
- 공통 reference height385.036988·표시 배율≈0.332435594473·cell-local 몸 root=[215.98656,386.727873]
- 평균 cap16.5/가슴등=[241.432321678,163.533531446]을 기존 idle cap32/가슴등=[214.619,151.143]·높이312/root=[194,332]에 맞춤
- alpha1–16 잔여30,699px·alpha>16 bbox2px여백·내부 fringe 유지·정확한 native64px 격자 아님

한 고정 배율과 공통 몸 root를8장 전체에 적용했다. 프레임별 피벗/배율 보정으로 높이 변화를 숨기지 않았다. capTop의 cell-local 실측은[15,17,15,16,16,21,16,16]이다. 실제 고정 배율을 곱한 상단 proxy 범위는1.994613567px로3px 상한 이내다. 다만1→2는0.664871189px,5→6는1.662177972px로 양반주기가 각각2px에 도달한 것은 아니다. 이 수치는 source alpha>16 경계의 환산값이며 신체 하중이나 사용자 체감의 측정값이 아니다.

## 검사와 한계

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s game/tests -q
.\.venv\Scripts\python.exe -B output/review/R1-W2/dummy_review.py
```

전체79/79·atlas/source 집중8/8 통과했다. 변경한 테스트 파일은 test_visual_atlas_r1b.py뿐이며 새8소스 기대·05f55ed 보존 기준을 반영하고 기존 선택/셀/root/ref/발점 검증을 유지했다. 동적 소스 nearest/canvas/종료/중간 실패 검사도 그대로 통과했다. 다른3방향/모든idle/기존7source사전·기존에셋파일 전체·core/locomotion/main/player_visual을 baseline과 정확 비교했다. git diff --check도 통과했다.

실제 PlayerVisual의 SDL dummy8장 선택·정지idle·source SHA 전후 동일을 확인했다. dummy-contact-sheet를 직접 확인했으며 원본/접촉 시트 준비 시 지휘에 경로를 즉시 전달했다. 근거는 output/review/R1-W2/의 dummy-contact-sheet.png, dummy-runtime-01.png부터08.png, dummy-review.json, alpha-review.json이다. 초기/교정1 alpha보고도 같은 폴더에 별도 보존했다.

최신 원본에서1/5·2/6 지지측 반전과 낮은 발 자세, 매우 얕은 지지무릎 변화·작은 어깨/상자 받침 차이가 보인다. 첫 원본의 깊은 관절 압축을 상한에 맞춰 줄인 결과이며 전체 PNG를 내려 흔드는 방식은 사용하지 않았다. 하지만 최종2/6의 변화는 작고 비대칭이며4/8 전진 자세도 비슷하다.4→5·8→1 발 위치 전환이 커질 가능성과 실제 접지 미끄러짐은 시간순 네이티브 검수 대상이다. 평평한 부츠나 상단 수치만으로 고정 접지·무게감 개선을 확정하지 않는다.

UI는 네이티브/GUI/물리 키보드 검수와 Git 조작을 하지 않았다. 통합 보고를 끝으로 모든 편집을 정지한다. 지휘의 전후 비교·기능 검수·커밋 뒤 사용자2차 확인을 기다리며 다른3방향/R2는 진행하지 않는다.
