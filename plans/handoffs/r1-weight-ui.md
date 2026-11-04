# R1-W1 UI·에셋 인계

기준일2026-11-05 · baseline a9723bc

## 비교 시안 연결 완료

front_right의 보행8장만 낮은 보행 후보로 교체했다. 기존 idle과 다른3방향 전체 frames, 기존6sources와 모든 기존 PNG/프롬프트를 정확히 보존했다. 최종4방향×9프레임/총36자세·7소스다. core/locomotion/main/player_visual 파일이 baseline과 바이트 단위로 같으므로90px/s·32px주기·8균등위상·입력/조준/충돌·재생 hold는 변경하지 않았다. 속도 답변은 미확정이며 이번 작업에서 결정하지 않았다.

내장 image_gen.imagegen·transparent_background=true로 기존 FR8장을 참조해 첫 후보 exec-21837ddf-1a14-434f-99d5-209f1f0652e4.png를 생성했다. 낮은 무릎/부츠는 개선됐으나1/5 지지 다리가 모호해 아래4자세의 다리만 표적 교정1회를 요청했다. 선택 출력 exec-46c16e90-f137-4517-ae1b-46a46826104d.png에서1/5 반전이 뚜렷해졌고 지휘가 한 방향 비교 시안으로 채택했다. 추가 생성은 하지 않았다.

- 파일 game/assets/player/r1-weight-front-right-20261105.png와 정확한 최초/교정 프롬프트 .prompt.txt
- 실제1774×887 RGBA, SHA256 D0330535D62B4586315AA373DF9F12538A7E125B6E534EB61B16F5A171AF57C6
- 생성 원본 픽셀 그대로 복사, 프로그램 그림 편집/반전/회전/복제/크로스페이드 없음
- source weight_front_right,4×2 실제 경계 x=[0,443,887,1330,1774]/y=[0,443,887]
- 공통 scale_reference_height388.314604·배율≈0.329629632·cell-local 몸 root=[214.581222,389.254427]
- 평균 cap top15.875/가슴등=[240.243589590,164.160150260]을 기존 idle cap32/가슴등=[214.619,151.143]·높이312/root=[194,332]에 맞춤
- alpha1–16 잔여52,096px, alpha>16 bbox2px여백 clip·내부 fringe 유지, 정확한 native64px 원본 아님

공통 몸 root와 한 배율을8장 전체에 적용했고 프레임별 bbox128px 정규화나 발바닥 평균 피벗을 사용하지 않았다. 기존 source는 비교용으로 보존했으며 smooth_front_right/front_steps의 참조가0이어도 삭제하지 않았다.

## 검사와 한계

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s game/tests -q
.\.venv\Scripts\python.exe -B output/review/R1-W1/dummy_review.py
```

전체79/79·atlas/source 집중8/8 통과했다. 다른3방향/모든idle/기존6source사전·기존에셋파일 전체·기본 움직임4개 파일을 baseline과 정확 비교해 보존했다. 실제 새8장 선택·공통ref/root·발점·셀·7소스nearest/canvas/단1회해제/중간실패 정리를 검사했다. git diff --check도 통과했다.

실제 PlayerVisual.draw의 SDL dummy-contact-sheet를 직접 확인했다. dummy8장 선택·정지idle·렌더 전후 source SHA 동일, clip 상단 proxy 차이0.329629632px를 기록했다. 근거는 output/review/R1-W1/의 dummy-contact-sheet.png, dummy-runtime-01.png부터08.png, dummy-review.json, alpha-review.json이다. 이 정렬 수치는 무게감·접지 통과를 뜻하지 않는다.

UI·독립 검토에서 높은 무릎/부츠 감소와 평평한 지지발,1/5 반전·3/7 지지측 차이를 확인했다. 그러나2/6의 지지 무릎/골반 하중 변화와4/8의 전진/체중 이동 구분은 작다. 상체의 실제 하중 수용이 강화됐다고 확정하지 않는다. 물리 지면 발트랙 주석이 없으므로2–4px clearance는 생성 목표이며 측정 달성값이 아니다. 실제 무게감·발 미끄러짐·주기 이음새·몸/장비 크기는 지휘의 전후 네이티브 비교와 사용자 판단 대상이다.

지휘 후속 통보: 새 메타로 전체79개·compileall·숨김 Windows native4시트/60프레임을 통과했다. 지휘가 runtime9자세 시트에서 낮아진 발 들림·1/5 반전·장비 손·몸 크기를 직접 확인했고, 동일 속도의 전후2초 비교 영상을 생성해 디코드를 확인했다. baseline의 다른3방향/모든idle/기존source·PNG와 core/main/logic/player_visual 코드의 정확 보존·SHA도 지휘가 확인했다. 이는 지휘 실행 결과를 전달받아 기록한 것이며 UI 네이티브 실행 결과가 아니다. 낮은 발 자세 확인과 실제 무게감 개선은 구분하며, 하중 수용·상체 체중 이동 변화가 작다는 한계는 유지한다.

이동 속도 질문은 여전히 미답변이므로90px/s를 유지했다. UI는 네이티브/GUI/물리 키보드 검수와 Git 조작을 하지 않았다. 이 기록 반영을 끝으로 모든 편집을 정지한다. 지휘의 문서 정리·중간 커밋 뒤 사용자2차 비교 확인을 기다리며 다른3방향 제작/R2는 진행하지 않는다.
