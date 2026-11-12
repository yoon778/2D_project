"""Delivery hints and result labels at the HUD's normal draw entry points."""
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from delivery import DeliveryWorld
import play_hud


class PlayHUDTests(unittest.TestCase):
    def setUp(self):
        self.world = DeliveryWorld()
        self.hud = play_hud.PlayHUD.__new__(play_hud.PlayHUD)
        self.hud.width, self.hud.height = 1280, 720
        self.hud._labels = {}
        self.hud._attack_label = None
        self.hud.reset_delivery()
        self.hud._vitals = Mock()
        self.hud._objective = Mock()
        self.hud._notice = Mock()
        self.hud._actions = Mock()
        self.light = Mock()

    def actions(self, *, visible=False):
        self.hud.draw(self.world, self.light, self.world.next_stop, focused=True, alarm=False,
                      near_visible_zombie=visible)
        return {key: text for key, text, _ in self.hud._actions.call_args.args[0]}

    def test_pickup_replaces_e_then_opening_map_and_sneaking_discard_hints(self):
        self.assertEqual(self.actions()["E"], play_hud.HINT_TEXT["E"])
        self.assertEqual(sum(key == "E" for key, _, _ in self.hud._actions.call_args.args[0]), 1)
        self.assertTrue(self.world.interact())
        self.assertEqual(self.actions()["M"], play_hud.HINT_TEXT["M"])
        self.hud.dismiss_hint("M")
        self.assertNotIn("M", self.actions())
        self.assertNotIn("Ctrl", self.actions())
        self.assertEqual(self.actions(visible=True)["Ctrl"], play_hud.HINT_TEXT["Ctrl"])
        self.world.sneaking = True
        self.assertFalse(self.hud.watch_for_sneak_hint(self.world))
        self.assertNotIn("Ctrl", self.actions(visible=True))

    def test_hints_expire_without_repeating_and_chase_does_not_spend_an_unseen_hint(self):
        self.assertIn("E", self.actions())
        self.world.elapsed_play_time = play_hud.HINT_DURATION
        self.assertEqual(self.actions()["E"], "택배 수령")
        self.assertTrue(self.world.interact())
        self.hud.dismiss_hint("M")
        self.world.zombie.state = "chase"
        self.assertFalse(self.hud.watch_for_sneak_hint(self.world))
        self.world.zombie.state = "idle"
        self.assertTrue(self.hud.watch_for_sneak_hint(self.world))
        self.world.elapsed_play_time = play_hud.HINT_WINDOW
        self.assertNotIn("Ctrl", self.actions(visible=True))

    def test_result_draws_stats_and_retry_releases_dynamic_count_label(self):
        self.world.result = "delivered"
        self.world.attack_count = 123
        with patch.object(self.hud, "_text") as text, patch.object(play_hud, "panel"), patch.object(play_hud, "fill"):
            self.hud.draw_result(self.world)
        labels = {args[0] for args, _ in text.call_args_list}
        self.assertTrue({"배달 성공", "배송지", "주택 뒷문", "남은 체력", "3 / 3", "공격 횟수", "123회",
                         "교전 없이 배달", "미달성", "Enter 같은 배송 재도전  ·  R 배달 선택  ·  Esc 종료"} <= labels)
        texture = object()
        key = ("123회", play_hud.BODY, play_hud.TEXT)
        self.hud._labels[key] = (texture, 40, 20)
        with patch.object(play_hud.p, "SDL_DestroyTexture") as destroy:
            self.hud.reset_delivery()
        self.assertNotIn(key, self.hud._labels)
        destroy.assert_called_once_with(texture)

    def test_two_stop_hud_uses_actual_target_and_keeps_both_results_on_failure(self):
        self.world = DeliveryWorld(two_stop_unlocked=True)
        self.assertTrue(self.world.select_contract(2))
        self.assertTrue(self.world.interact())
        shop, rear_door = self.world.contract.stops
        self.world.player.x, self.world.player.y = rear_door.position
        self.light.contains.side_effect = lambda position: position == rear_door.position
        self.assertEqual(self.actions()["E"], "택배 전달")
        self.light.contains.assert_called_once_with(rear_door.position)
        self.assertTrue(self.world.interact())

        with patch.object(self.hud, "_text") as text, patch.object(play_hud, "panel"), patch.object(play_hud, "fill"):
            play_hud.PlayHUD._objective(self.hud, self.world)
            self.assertIn("1 / 2", {args[0] for args, _ in text.call_args_list})
            text.reset_mock()
            self.world.player_hp = 0
            self.world.result = "defeated"
            self.hud.draw_result(self.world)
        labels = {args[0] for args, _ in text.call_args_list}
        self.assertTrue({"배달 실패", f"{shop.name} · 미완료", f"{rear_door.name} · 완료"} <= labels)

    def test_first_success_result_announces_new_contract(self):
        self.assertTrue(self.world.interact())
        self.world.player.x, self.world.player.y = self.world.destination
        self.assertTrue(self.world.interact())
        with patch.object(self.hud, "_text") as text, patch.object(play_hud, "panel"), patch.object(play_hud, "fill"):
            self.hud.draw_result(self.world)
        labels = {args[0] for args, _ in text.call_args_list}
        self.assertIn("새 계약 열림 · R에서 3번 선택", labels)
