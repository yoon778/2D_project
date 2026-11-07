# R2-SW 명중 상태 인계

기준선 `29a659f`에서 `Attack.landed: bool = False`를 마지막 필드로 추가했다. `.18초`에 거리·방향·벽 판정을 통과해 좀비 HP가 감소할 때 `True`가 된다. 마지막 타격도 현재 공격에 기록되며 다음 공격은 `False`에서 시작한다. `_hit_done`은 시도 여부다.

`test_combat.py`의 기존 검사에서 타격 직전/직후, 헛스윙/벽, 마지막 타격과 연속 공격 초기화를 확인했다. 판정·이동 검사 31개와 기존 위치 인자 4개 호출을 통과했다.

```powershell
.venv/Scripts/python.exe -B -m unittest game.tests.test_combat game.tests.test_attack_walk_logic game.tests.test_zombie_attack_logic_r2za
```

`combat.py`와 `test_combat.py` 담당 파일 동결. 앞오른쪽 `.18~.24초` 표시 비교는 지휘 검수 범위다.
