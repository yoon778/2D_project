# Dead Route (데드 루트)

좁은 골목에서 좀비의 시야와 소음을 피해 택배를 배달하고, 트럭으로 돌아오는 2.5D 도트 게임

## Windows에서 실행

1. [게임 소스 ZIP 다운로드](https://github.com/yoon778/2D_project/archive/refs/heads/planning/first-presentation.zip) 또는 GitHub의 **Code → Download ZIP**
2. 압축을 풀고 `game` 폴더와 `README.md`가 보이는 폴더를 엶. 파일 탐색기 주소창에 `powershell`을 입력하고 **Enter**
3. [Windows용 Python 3.13](https://www.python.org/downloads/windows/) 설치 후 아래 명령을 한 줄씩 실행

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r game/requirements.txt
.\.venv\Scripts\python.exe game/main.py
```

두 번째 실행부터는 마지막 줄만 실행. 창으로 플레이하려면 마지막 줄 끝에 `--windowed` 추가

## 첫 배달

1. 오프닝이 끝나길 기다리거나 **Enter**로 건너뛰기
2. **1·2·3·4** 또는 운송장 클릭으로 계약을 고른 뒤 **Enter** 또는 **출발** 클릭
3. 트럭 짐칸 앞에서 **E 0.5초**로 택배 수령. **M** 지도의 붉은 배송지를 찾아 배송함마다 **E 1초**로 전달
4. 모든 배송 후 지도의 초록 트럭으로 복귀. 추격을 끊고 운전석 앞에서 **E 0.7초**로 탑승하면 출차 후 결과 영수증 표시

| 계약 | 배송지 | 기믹과 우회로 |
| --- | --- | --- |
| **1** 정비창 왕복 | 2곳 | 철문 열기 또는 서쪽 골목 우회 |
| **2** 물류창고 왕복 | 2곳 | 방송을 켜 좀비 유인 또는 서쪽 통로 우회 |
| **3** 대피소 실내 배달 | 1곳 | 남쪽 출입구로 들어가 실내 보급실에 배달 |
| **4** 상점 왕복 | 3곳 | 경비초소 열쇠 → 관리실 회로 → 다리 지름길 또는 동쪽 골목 우회 |

## 조작키

| 입력 | 행동 |
| --- | --- |
| **WASD** / **Shift** / **Ctrl** | 이동 / 달리기 / 조용히 걷기 |
| **마우스** / **좌클릭** | 손전등과 조준 / 배트 휘두르기 |
| **E 길게** | 수령·전달·장치 작동·탑승. 진행 중 키를 떼거나 움직이거나 맞으면 취소 |
| **F** / **Q** | 빈 병 줍기 / 마우스 방향으로 던져 좀비 유인 |
| **M** | 지도 열기·닫기. 파란 화살표는 내 위치, 노란 점은 지금 사용할 수 있는 장치 |
| **지도 좌클릭** / **우클릭** / **Space** | 경유지 추가 / 마지막 경유지 삭제 / 현재 경유지 건너뛰기 |
| **Tab** / **회로판 1·2·3** | 4번 지도 확대·전체 전환 / 회로 타일 회전 |
| **Esc** | 열린 지도·쪽지·회로 닫기 또는 일시정지. 일시정지 메뉴에 조작법·소리·화면 배율 설정 |
| **결과 화면 Enter** / **R** | 같은 계약 재도전 / 계약 다시 선택 |

## 프로젝트 자료

- [상세 실행과 조작, 리소스 출처](SUBMISSION.md)
- [기획서](PRD.md) · [개발·검수 기록](plans/weekly-development-log.md) · [발표 자료](presentation/README.md)
- 제출용 ZIP 생성은 `py -3.13 tools/package_submission.py`. 결과는 `output/submit/Dead_Route.zip`
