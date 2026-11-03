# 임시 리소스

- 캐릭터·맵·모션: pico2d 도형으로 코드에서 표시, 정식 아트 미적용
- audio/attack.wav, hit.wav, hurt.wav, zombie_step.wav, zombie_groan.wav: 이 프로젝트용으로 합성한 임시 효과음, 외부 음원 사용 없음
- 글꼴: 설치한 pico2d 패키지의 ConsolaMalgun.ttf 사용, 별도 폰트 복사 없음

## 주인공 아틀라스 검수 원본 — 2026-11-03

- 파일: [player/courier-atlas-20261103-v1.png](player/courier-atlas-20261103-v1.png)
- 출처: 내장 `image_gen.imagegen`으로 이 프로젝트용 생성. 외부 원본 이미지 입력 없음. `transparent_background=true` 요청.
- 규격: 1536×1024px, 8bit RGBA, 3열×2행의 512×512px 셀. 원본을 그대로 복사했으며 픽셀 편집·리사이즈·배경 제거를 하지 않음.
- 프롬프트 요약: 오른쪽을 향하는 수직 탑뷰 배달원, 어두운 청록 작업복과 작은 주황 반사띠, 몸·머리·가슴등 / 팔·손 / 부츠 / 갈색 택배 / 목재 방망이를 다섯 셀에 분리하고 우하단 셀은 비움. 단순한 윤곽, 투명 배경, 글자·로고·그림자·광륜 금지.
- 정확한 생성 프롬프트: [player/courier-atlas-20261103-v1.prompt.txt](player/courier-atlas-20261103-v1.prompt.txt)
- 원본 SHA256: `19433270B1DFC4A5ED2B4809224939D7FBAC2D9013B8DC9B293FB7000950E9C5`
- 검수: 정수리·어깨를 보는 탑뷰와 다섯 부위 분리는 육안 확인. 실제 알파 존재, 전체 1,572,864px 중 알파 0은 1,317,003px. 저알파 광륜이 남고 우하단 빈 셀에도 알파 1인 292px이 있어 완전한 무잔여 원본으로 판정하지 않음.
- 상태: 지휘 검수용 첫 후보. 표시 크기는 미확정이며 실제 게임 크기·회전·모션 검증과 main.py 연결은 아직 진행하지 않음.
