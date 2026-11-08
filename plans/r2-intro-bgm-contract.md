# R2-INTRO · 오프닝과 배경음악

2026-11-08 · 2주차

- 시작 시 8초 도트 오프닝. 마지막 택배 송장, 가슴등, 골목 끝 좀비 순서. Enter로 스킵하고 게임 조작으로 연결. R 재시작은 바로 게임으로 복귀.
- 오프닝 중 이동·타격·좀비 판정 정지. Esc와 창 닫기는 즉시 종료. 오프닝에서 입력한 이동·공격은 첫 플레이 프레임으로 넘기지 않음.
- `game/assets/audio/last-delivery.mp3`를 한 채널에서 반복 재생. 오프닝 이후 탐색 음량을 낮추고, 살아 있는 좀비와 가까워질수록 더 낮춤. 포커스가 없으면 일시 정지. 음원·오디오 장치 사용 불가 시 게임 진행.
- 음원은 Suno Free로 제작·다운로드한 [Last Delivery](https://suno.com/song/b5687c1a-2534-4665-af87-6908db42325d), 비상업 검수용. [Suno 다운로드 조건](https://help.suno.com/en/articles/13876865)
- UI는 `game/main.py`, `game/opening.py`, 관련 UI 검사. 로직은 `game/spatial_audio.py`, 관련 음향 검사. 지휘는 음원 배치·통합·검수·Git. 기존 전투·이동·아틀라스는 다른 작업 묶음과 분리.
- 인터페이스는 `BackgroundMusic(path)`, `start()`, `update(dt, *, distance=None, opening=False, focused=True)`, `close()`. 거리 단위는 지면 px, 죽은 좀비는 `None`.
- 지휘 검수는 시간 만료·Enter 스킵·R 재시작·위험 거리 음량·무음 대체·종료 정리. 자동 입력과 실제 사용자 청취는 구분.

## 지휘 1차 검수

- Windows SDL 숨김 창에서 실제 3컷 렌더와 8.01초 뒤 본편 전환 확인
- SDL 이벤트로 Enter 스킵, 오프닝 중 입력 폐기, 본편 WASD 및 R 재시작 확인
- 실제 MP3 파일을 SDL dummy 믹서로 재생하고 음량 32 → 22 → 8 확인. 장치·음원 없음, 포커스, 종료 정리까지 포함한 전체 자동 검사 182개 통과
- 증거는 `output/review/suno-bgm/`의 `01-label.png`, `02-light.png`, `03-alley.png`, `gameplay.png`, `native.json`
- 사용자 2차 확인은 오프닝 흐름과 실제 출력 장치에서의 음량 차이
