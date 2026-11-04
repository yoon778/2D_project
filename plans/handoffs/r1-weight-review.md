# 1주차 R1-W1 낮은 보행 시안 검수

기준일: 2026-11-05 · baseline a9723bc
상태: 앞·오른쪽 자세 시안 적용·지휘 기술 검수 통과, 사용자 비교 확인 대기
사용자 `좀보이드처럼 모션이 무게감 있었으면` 피드백과 [시안 계약](../r1-weight-contract.md) 기준

## 선택과 작업

- 속도 유지/감속 질문은 미답변. 기존90px/s·32px 거리 주기·8장 균등 위상 유지
- 주기는32/90≈0.35556초. 재생만 늦춰 발 미끄러짐이 커지는 변경 대신 자세를 먼저 분리 비교
- front_right만 높은 무릎/부츠 들림을 낮추고 지지 발바닥·낮은 통과·상자 운반 자세로 교체
- 첫 그림은 낮은 발은 개선됐지만1/5 교대가 모호해 아래4자세를 표적 교정1회
- 교정 원본과 독립 시각 검토에서1/5·3/7·4/8 다리 실루엣 구분 개선, 낮은 발 들림·장비 손·정체성 유지 확인
- `a5af4d6`: 시안 계약, `01507fa`: 새FR8장·메타·보존 회귀·담당 보고

## 실제 기술 검수

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s game/tests -q
.\.venv\Scripts\python.exe -m compileall -q game
.\.venv\Scripts\python.exe -B output/review/R1-W1/native_review.py --direction front_right
```

- 전체79/79·compileall 통과
- 다른3방향 전체 frames·모든idle·기존6sources·기존PNG와 기본 코드4개를 baseline과 정확 비교, SHA 일치
- 최종36자세·7소스, 실제 frame 선택·정지 idle·nearest·크기/셀/clip/고정 배율/root·다중 텍스처 정리 회귀 유지
- 숨김 Windows SDL 실제 렌더4장·실제 core 거리 연동60프레임, SDL 완전 종료·검수 중 파일 SHA 보존
- 지휘가 실제 크기9자세 시트에서 낮아진 부츠/무릎·1/5 구분·몸/장비 크기를 확인
- 머리 상단 높이 차이 proxy0.32963px. 발의 실제 지면 clearance 측정치가 아님
- 전후 비교 영상: 같은90/32·2초/60프레임 실제 렌더를 각각 잘라 nearest2배 확대·좌우 배치, FFmpeg 전체 디코드 통과
- 원래 게임 코드는 불변. 직전1주차 표시창 성능 결과는 baseline 측정 이력이며 이 시안의 FPS를 새로 측정한 결과로 바꾸어 기록하지 않음

로컬 증거: output/review/R1-W1/before-native.mp4, after-native.mp4, weight-walk-comparison.mp4, front_right/native-review.json, front_right/native-contact-sheet.png
비교 영상 왼쪽은 기존, 오른쪽은 시안. 캡처30FPS는 앱의 실제 성능 수치가 아님

## 한계·사용자 비교

1/2·5/6의 하중수용 변화와 상체/골반이 눌리는 변화는 미세함. 무게감이 충분히 개선됐다고 확정하지 않음
2–4px 낮은 발 clearance는 생성 목표이며 실제 지면 트랙으로 측정 달성한 수치가 아님
일부 다리 겹침과 낮은 알파 가장자리 잔여가 남음. 완전한 발 고정이나 미끄러짐 해결을 보증하지 않음
실제 연속 보행의 느낌·착지 버팀·발 미끄러짐·8→1은 사용자2차 비교 확인 대상

프로젝트 루트에서 `.\.venv\Scripts\python.exe game/main.py` 실행, 앞·오른쪽으로 조준해 걷기/후진/옆걸음/정지 재출발 확인
시안 비교 후 다른3방향의 자세 확장 또는 박자/보폭 재검토 범위를 결정. R2·푸시는 미착수
