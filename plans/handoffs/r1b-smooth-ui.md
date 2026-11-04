# R1-B-S1 UI·에셋 인계

기준일: 2026-11-05

## 현재 결과

front_right의 기존 idle을 유지하고 실제 선택 가능한 보행 8장을 연결했다. 다른 세 방향의 전체 프레임 사전과 기존 sources, 기존 PNG 해시는 보존했다. PlayerVisual.frame_index가 현재 방향의 보행 장수를 Locomotion.walk_frame_index에 전달하며 draw도 이 속성으로 그림을 선택한다. main.py·입력·이동 속도·충돌·stride는 변경하지 않았다.

UI 소스·메타데이터 편집을 마무리했다. 지휘가 숨김 Windows 렌더·시간순 검수를 완료했다고 전달했다. 이 인계 갱신을 끝으로 모든 편집을 정지한다. UI는 Git 조작과 네이티브/GUI 창 실행을 수행하지 않았다.

## 제작과 원본

- 선택 파일: game/assets/player/r1b-smooth-front-right-20261105.png
- 정확한 최초/교정 프롬프트: 같은 이름의 .prompt.txt
- 도구: 내장 image_gen.imagegen, transparent_background=true
- 최초 생성: exec-6e2b9f38-bfb4-483e-9577-794bae88952f.png, 앞뒤 반주기의 선행 다리 반복으로 미채택
- 표적 교정 1회: exec-6b8dd425-efad-424b-b479-716b6d076e47.png, 허리 아래 다리 자세 교정 요청
- 참조: 기존 r1b-courier-atlas-20261104.png와 r1b-front-step-corrections-20261104.png. 교정은 최초 출력과 기존 교정 그림의 왼쪽 FR 자세를 참조했다.
- 지휘가 교정본 1/5의 반대 다리 전진을 직접 확인하고 채택했다. 이후 추가 생성은 하지 않았다.
- 실제 원본: 1774×887 RGBA, SHA256 B788C200FFC000D225CF228769CEA01FE5F5BBA2AB79EF52FF77CF0012B3D667
- 생성 원본을 그대로 복사했다. 프로그램으로 그림 픽셀을 편집하지 않았다. 정확한 64px 원본 격자가 아니다.

## 셀·배율·몸 기준점

새 source ID는 smooth_front_right다. 4열×2행의 실제 정수 경계는 x=[0,443,887,1330,1774], y=[0,443,887]이다. 셀 크기는 443/444px가 섞이므로 동일 정수 cell_size로 가정하지 않았다. 각 프레임의 실제 cell/clip/pivot을 기존 JSON의 front_right.frames와 새 source에 기록했다.

8장 모두 scale_reference_height=384.902697, 표시 배율=128/384.902697≈0.33255158을 사용한다. 각 bbox 높이로 정규화하지 않는다. 공통 셀 로컬 몸 root=[215.049613,387.098747]이며 해당 셀 원점만 더했다. 원래 idle의 머리 top=32·가슴등=[214.619,151.143]과 새 sheet의 머리 top=17·평균 가슴등=[240.4865,163.98225]의 간격으로 배율과 root를 맞췄다. 프레임별 발바닥 평균으로 root를 바꾸지 않았다.

알파 읽기 분석에서 alpha1–16 픽셀은 58,788개였다. clip은 alpha>16 bbox에 2px 여백을 두며 clip 내부의 저알파 가장자리는 원본 그대로 남는다. 더미 렌더의 8장 clip 상단 높이 차이는 0px다. 이는 정렬 보조 수치이며 보행 품질 통과를 뜻하지 않는다.

## 검사와 증거

아래 명령은 프로젝트 루트에서 실행했다.

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s game/tests -q
.\.venv\Scripts\python.exe -B output/review/R1-B-S1/dummy_review.py
```

전체 자동 검사 74/74 통과. 집중 검사는 atlas 4개·source 4개·main 루프/보행 연결 7개 통과했다. front_right 보행 8장 실제 선택과 키 해제 후 idle, 기존 방향 유지, 새 4×2 셀/공통 배율/고정 발점, 세 소스 nearest/실제 canvas, 한 번 해제·중간 로드/크기 실패 정리를 확인했다. 기존 세 방향의 프레임 전체 사전·FR idle·기존 sources·그 밖의 메타 필드와 기존 PNG 해시도 변경 전 Git 내용과 정확 비교했다.

- output/review/R1-B-S1/dummy-contact-sheet.png: 실제 PlayerVisual.draw로 그린 시간순 8장
- output/review/R1-B-S1/dummy-runtime-01.png부터 08.png: 같은 표시 위치의 순서별 실제 SDL 더미 캡처
- output/review/R1-B-S1/dummy-review.json: 실제 선택·배율·root·소스 해시 전후 동일·정지 idle 기록
- output/review/R1-B-S1/dummy-cycle.mp4: 위 8개 캡처를 22.5fps로 반복 인코딩한 1280×720·72프레임·3.2초 검토본

영상은 90px/s·32px stride에서 8장 자세 전환 빈도인 22.5fps로 캡처를 반복한 것이다. 실시간 main 루프 녹화나 물리 키보드 검수 영상은 아니다. 더미 렌더 스크립트도 실제 사용자 입력을 검증하지 않는다.

## 남은 시각 판단

독립 검토에서도 1/5의 선행·지지 다리 반전은 확인했다. 3/7의 골반·무릎 겹침으로 좌우 다리 추적에 한계가 있고 4/8의 상승 부츠 실루엣은 비슷하다. 자동 검사와 머리 높이 수치만으로 보행 품질 통과를 주장하지 않는다.

지휘의 후속 통보: 전체 74개 검사, 숨김 Windows 네이티브 4개 시트와 실제 거리 연동 60프레임 sequence 검수 성공. 지휘가 smooth-contact-sheet에서 8자세·반주기 전환·상체 정렬을 직접 확인했다. 지휘의 FR 머리 상단 proxy 차이는 0.1554px이며 UI 더미의 clip 상단 차이 0px와는 측정 대상이 다르다. baseline 3f9620c 대비 기존 idle·다른 세 방향 프레임·기존 PNG 3개 보존도 지휘가 별도 확인했다. 이는 지휘 실행 결과를 전달받아 기록한 것이며 UI의 네이티브 실행 결과가 아니다. 실제 조작감과 해부학적 세밀 차이는 사용자 2차 확인 대상이다.

지휘 1차 검수·수정·중간 커밋 후 사용자 2차 확인에서 정지한다. 다른 방향 확장·공격·R2는 이번 작업에 포함하지 않았다.
