# Dead Route 실행 안내

Windows에서 Python 3.13을 설치하고 ZIP을 푼 뒤 `Dead_Route` 폴더에서 PowerShell을 엽니다.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r game/requirements.txt
.\.venv\Scripts\python.exe game/main.py
```

- Enter로 오프닝을 건너뜁니다. WASD로 이동하고 Shift로 달립니다.
- 마우스로 길을 비춥니다. 좀비가 가까이 오면 왼쪽 클릭으로 공격할 수 있습니다.
- M으로 지도를 열면 큰길·골목, 상점·정류장, 현재 위치·수령지·배송지를 볼 수 있습니다. 지도를 보는 동안 게임은 일시정지됩니다.
- 남서쪽 거점에서 E로 택배를 받습니다. 북동쪽 배송함 가까이에서 E를 누르면 배달에 성공합니다.
- 체력이 0이면 실패합니다. R로 다시 시작하고 Esc로 종료합니다.

`PRD.md`는 게임 기획서입니다. `game/`에는 실행 코드, 설치 목록, 게임이 읽는 이미지·음원·스프라이트 데이터가 들어 있습니다.

## 리소스 출처

- 배달원·좀비 원화는 ImageGen을 사용했습니다. 배달원 모션과 빈손 변형은 프로젝트의 스프라이트 제작 코드로 합성했습니다.
- ZIP의 `sources/`에 배달원과 좀비 원화 생성 프롬프트가 들어 있습니다.
- 골목 쓰레기통과 일부 좀비 보행에는 PixelLab을 사용했습니다.
- 마을의 도로, 주택, 상점, 정류장, 가로등은 프로젝트의 도트 에셋 제작 코드로 생성했습니다.
- 좀비 발소리와 신음은 프로젝트의 합성 효과음입니다.
- 오프닝·게임 배경음악은 Suno Free로 생성한 비상업 과제용 음원입니다. [Last Delivery](https://suno.com/song/b5687c1a-2534-4665-af87-6908db42325d)
- 화면 글꼴은 pico2d에 포함된 `ConsolaMalgun.ttf`를 사용합니다.
