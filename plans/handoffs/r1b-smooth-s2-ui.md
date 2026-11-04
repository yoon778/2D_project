# R1-B-S2 UI·에셋 인계

기준일: 2026-11-05 · baseline 358978f

## back_right: 지휘 검수·중간 커밋 완료 이력

back_right만 기존 idle+보행8장으로 연결했다. 현재 FR9/BR9/BL3/FL3, 총24자세·4소스다. S1 front_right 전체 frames/source, 모든 idle, 미진행 back_left/front_left 전체 frames, 기존 sources/PNG와 그 밖의 메타 필드는 baseline과 정확히 보존했다. PlayerVisual의 기존 N장 API를 재사용했으며 helper·main·core·locomotion은 변경하지 않았다.

첫 생성 exec-5d27882c-a4f4-420c-b1b7-71295a4c7cc9.png는 양 반주기에서 같은 다리가 반복되어 미채택했다. 아래4자세의 다리만 표적 교정한 exec-ffa3db12-9b72-4919-962e-29d175474e94.png를 선택했다. 지휘와 독립 시각 검토에서1/5·3/7 지지 다리 반전을 확인했다. 등/가방, 오른손 방망이, 몸 앞 상자의 자연 가림을 유지했다. 4/8 상승 부츠는 유사하며 주기 이음새·접지·실제 부드러움은 시간순 네이티브 검수 대상이다. 추가 생성은 하지 않았다.

- 에셋: game/assets/player/r1b-smooth-back-right-20261105.png
- 정확한 최초·교정 프롬프트: 같은 이름의 .prompt.txt
- 도구: 내장 image_gen.imagegen, transparent_background=true, 생성일2026-11-05
- 참조: 기존12자세 atlas와 S1 front_right8장. 교정은 최초sheet와 기존atlas의 BR 반대지지 자세를 참조했다.
- 실제1774×887 RGBA, SHA256 201FCE1A74C302B0B180D52AB168ED84E6B04BFD5192A6063A00C19041F790AF
- 생성 픽셀을 그대로 복사했다. 프로그램 그림 편집·반전·회전·복제·크로스페이드를 하지 않았다. 정확한 native64px 격자가 아니다.

source ID는 smooth_back_right다. 4×2 실제 경계는 x=[0,443,887,1330,1774], y=[0,443,887]이며 셀별 clip/root/cell을 JSON에 기록했다. 모든8장에 공통 scale_reference_height=410.339432, 배율≈0.311936875, cell-local 몸 root=[224.937789,414.854546]을 사용했다. 평균 cap top17.625와 평균 가방 주황 flap=[181.088154895,155.774203814]를 기존 BR idle cap391/flap=[148.552238806,496.377883311]·root=[182,694]·높이313에 맞췄다. 같은 가방 flap의 최대 주황 연결군을 분석했으며 발바닥 평균이나 프레임별 bbox128px 정규화는 사용하지 않았다.

알파1–16은68,773px다. clip은 alpha>16 bbox에2px 여백을 두고 내부 저알파 fringe는 원본대로 남겼다. UI 더미의 clip 상단 차이는0.311936875px이며 실제 부드러움 통과와 구분한다.

## 검사·근거

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s game/tests -q
.\.venv\Scripts\python.exe -B output/review/R1-B-S2/dummy_review.py --facing back_right
```

전체79/79 통과. 집중 검사 atlas4·source4·실제 main 루프 연결7개도 통과했다. 실제 dummy main 루프에서 FR/BR8장을 모두 선택하고 KEYUP idle로 돌아오는 것을 확인했다. 테스트의 S1 장수/소스수 고정을 중간 상태에 맞게 확장하되 S1 FR·모든 idle·미진행 방향의 전체 사전 canonical SHA와 원본 PNG SHA 검증을 유지했다. 추가 방향은 순서대로8장, 대기 방향은 기존2장을 검사한다. 동적 소스의 nearest·실제canvas·단1회해제·중간 크기/로드 실패 정리 검증도 유지했다.

output/review/R1-B-S2/back_right/의 dummy-contact-sheet.png, dummy-runtime-01.png부터08.png, dummy-review.json, alpha-review.json이 근거다. alpha_analysis.py는 PNG 읽기 분석만 수행한다. 더미8장 실제선택·정지idle·렌더 전후 원본SHA 동일을 확인했다. git diff --check도 통과했다. UI는 네이티브/GUI·물리 키보드 검수를 수행하지 않았고 Git 조작도 하지 않았다.

이후 지휘가 전체79개·숨김 native4시트/60프레임/8→1캡처·기존 그림/메타 보존을 확인하고 중간 커밋을 완료했다고 전달했다. 지휘의 back_left 착수 지시로 아래 두 번째 방향을 진행했다. 이 네이티브 결과는 지휘 실행이며 UI는 더미만 실행했다.

## back_left: 지휘 검수·중간 커밋 완료 이력

착수 기준9b6bb29에서 back_left만 idle+walk8로 연결했다. 현재 FR9/BR9/BL9/FL3, 총30자세·5소스다. FR/BR 전체 frames/source/PNG, 모든 idle, 미진행 FL 전체 frames와 그 밖의 메타를 기준 커밋과 정확 비교해 보존했다. 기존 N장 연결을 재사용했으며 helper/main/core/logic은 변경하지 않았다.

최초 exec-5a03ecfd-d344-4ebe-88c9-e97be7a87610.png는1/5 동일 지지 다리·4/8 유사 자세로 미채택했다. frame5/8의 허리 아래만 표적 교정 요청한 exec-7288527d-cd2e-44c9-9dba-857c28b92132.png를 연결했다. UI와 독립 검토에서1/5·3/7 지지/굽힌 다리 반전을 확인했다. 뒤왼쪽 시점과 왼손 몸 앞 상자·오른손 방망이를 유지했다. 4/8 상승 실루엣 유사성은 남으며 연속 보행·8→1·접지는 지휘 시간순 검수 대상이다. 추가 생성은 하지 않았다.

- 내장 image_gen.imagegen·transparent_background=true, 최초1회·표적 교정1회, 생성일2026-11-05
- 파일 game/assets/player/r1b-smooth-back-left-20261105.png와 정확 프롬프트 .prompt.txt
- 실제1774×887 RGBA, SHA256 1B6FB22C7B8E5DA37EEF6EE89BD0168378AAD8653B554BB09A8F43F455728558
- 생성 원본 픽셀 그대로 복사, 프로그램 그림 편집/반전/회전/복제 없음
- source smooth_back_left, 실제4×2 경계 x=[0,443,887,1330,1774]/y=[0,443,887]
- 8장 공통 reference height406.824058, 배율≈0.314632327, cell-local 몸 root=[223.813893,404.934783]
- 평균 cap top12.5/가방 flap=[262.992928339,146.516700635]를 기존 BL idle cap754/flap=[218.950736,856.450170]·높이311/root=[189,1054]에 맞춤
- alpha1–16 잔여59,820px, alpha>16 bbox2px여백 clip, 정확한 native64px격자 아님

아래 명령으로 전체79/79 통과, atlas4/source4 집중 검사도 통과했다. 테스트는 FR/BR/BL9·FL3을 강제하고 기존 BR 전체 frames/source/PNG의 canonical SHA 동결 검증을 추가했다. 더미에서 BL8장 실제선택·정지idle·원본SHA 전후 동일·clip 상단 차이0.314632327px를 확인했다. 정렬 수치와 실제 모션 품질 판정은 구분한다.

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s game/tests -q
.\.venv\Scripts\python.exe -B output/review/R1-B-S2/dummy_review.py --facing back_left
```

근거는 output/review/R1-B-S2/back_left/의 dummy-contact-sheet.png, dummy-runtime-01.png부터08.png, dummy-review.json, alpha-review.json이다. UI가 더미 시트를 직접 확인했으며 git diff --check도 통과했다. 네이티브/GUI/물리 키보드/Git 조작은 하지 않았다.

이후 지휘가 전체79개·숨김 native4시트/60프레임/8→1캡처와 기존 메타 보존을 확인하고 중간 커밋을 완료했다고 전달했다. 지휘의 최종 front_left 지시로 아래 마지막 방향을 진행했다.

## front_left: 최종36자세 연결·편집 정지

착수 기준2e44658에서 front_left만 idle+walk8로 연결했다. 최종 네 방향 모두9프레임으로 총36자세·정확6소스다. 사용되지 않게 된 front_steps도 기존 메타/PNG 그대로 보존했다. FR/BR/BL 전체 frames/source/PNG와 모든 idle을 고정했으며 기존 N장 API를 재사용했다. helper/main/core/logic 변경은 없다.

첫 생성 exec-242b4146-825a-407c-a94d-813ae35b608f.png를 UI·독립 검토·지휘가 채택했다. 1/5 선행 다리·3/7 지지/굽힘·4/8 상승 부츠의 반대 교대와 중간 자세를 확인했다. 앞왼쪽 사선·일부 얼굴/가슴·왼팔 몸 앞 상자(screen right)·오른손 방망이(screen left)·가슴등 정체성을 유지했다. 생성1회이며 교정이나 추가 생성은 하지 않았다.

- 내장 image_gen.imagegen·transparent_background=true, 생성일2026-11-05
- game/assets/player/r1b-smooth-front-left-20261105.png와 정확 프롬프트 .prompt.txt
- 실제1774×887 RGBA, SHA256 D3DCD3D3FF13BE1EB03C3C07D27087ACE3824535EC592DACB7BFBF625958B5F1
- source smooth_front_left, 실제4×2 경계 x=[0,443,887,1330,1774]/y=[0,443,887]
- 8장 공통 reference height380.295367·배율≈0.336580487·cell-local 몸 root=[219.869849,385.992414]
- 평균 cap top18.125/가슴등=[198.564608528,171.610221546]을 기존 idle cap1116/가슴등=[162.857,1239.5]·높이306/root=[180,1412]에 맞춤
- alpha1–16 잔여52,208px·alpha>16 bbox2px여백·원본 픽셀 그대로 복사·정확한 native64px 격자 아님

자체 집중 검사 atlas4/source4/실제 main 루프7개가 통과했다. 최종4방향×9·36자세·정확6소스, 이전 BL 전체 사전/PNG 동결과 FR/BR/모든 idle 보존을 검사했다. 실제 SDL dummy main 루프에서 네 방향 모두8장 선택→KEYUP idle을 확인했다. FL 더미8장 렌더·정지idle·렌더 전후 원본SHA 동일·clip 상단 차이0.336580487px를 기록하고 시트를 직접 확인했다. 실행은 기존 dummy_review.py의 --facing front_left다. 근거는 output/review/R1-B-S2/front_left/의 dummy-contact-sheet.png, dummy-runtime-01.png부터08.png, dummy-review.json, alpha-review.json이다.

지휘 후속 통보로 전체79개·이전2e44658 대비 보존 검사·숨김 Windows native4시트/60프레임을 통과했다. 지휘가 원본8장·게임 크기 시트·8→1캡처를 직접 검토했다. 이는 지휘 실행 결과이며 UI는 네이티브/GUI·물리 키보드·Git 조작을 하지 않았다. 정렬 수치/정지 그림/자동 검사는 세밀한 해부학과 실제 조작 체감을 대신하지 않는다. 저알파 가장자리와 프레임별 미세 색/형태 차이가 남는다.

S2 세 방향 UI 작업을 모두 마무리했으며 이 인계 갱신을 끝으로 모든 편집을 정지한다. 지휘가 전체 native/실제 main 성능QA·문서·커밋을 이어간다. 재현 문제의 후속 수정 요청 전에는 추가 변경하지 않는다. 전체 S2 뒤 사용자2차 확인이며 R2는 진행하지 않았다.
