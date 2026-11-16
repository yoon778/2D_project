"""Delivery status, contextual prompts, pause pages and receipts."""
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
        self.hud._waypoint_label = None
        self.hud.reset_delivery()
        self.hud._vitals = Mock()
        self.hud._objective = Mock()
        self.hud._notice = Mock()
        self.light = Mock()

    def test_normal_hud_keeps_status_without_drawn_actions_after_pickup(self):
        self.assertTrue(self.world.interact())
        with (patch.object(self.hud, "draw_action_prompt") as prompt,
              patch.object(self.hud, "_text") as text):
            self.hud.draw(self.world, self.light, self.world.next_stop, focused=True, alarm=False)
        self.hud._vitals.assert_called_once_with(self.world)
        self.hud._objective.assert_called_once_with(self.world)
        prompt.assert_not_called()
        text.assert_not_called()

    def test_head_prompt_uses_y_up_and_shows_progress_in_one_badge(self):
        with (patch.object(self.hud, "_label", return_value=(None, 48, 24)),
              patch.object(self.hud, "_keycap") as cap, patch.object(self.hud, "_text") as text,
              patch.object(play_hud, "panel") as panel, patch.object(play_hud, "fill") as fill):
            self.hud.draw_action_prompt(640, 440, "E", "택배 수령 중", progress=.25)
        left, top, width, height = panel.call_args.args
        self.assertLessEqual(top + height, 719 - 440 - 9)
        self.assertLessEqual(abs(left + width / 2 - 640), 1)
        cap.assert_called_once_with("E", left + 5, top + 4, 60)
        text.assert_called_once_with("택배 수령 중", left + 73, top + 16, play_hud.BODY)
        self.assertEqual(fill.call_args_list[0].args[:4], (left + 5, top + 33, width - 10, 4))
        self.assertEqual(fill.call_args_list[1].args[:4], (left + 5, top + 33, round((width - 10) * .25), 4))

    def test_prompt_moves_to_one_side_when_head_is_too_close_to_top(self):
        with (patch.object(self.hud, "_label", return_value=(None, 46, 20)),
              patch.object(self.hud, "_keycap"), patch.object(self.hud, "_text"),
              patch.object(play_hud, "panel") as panel, patch.object(play_hud, "fill") as fill):
            for x in (15, 1265):
                self.hud.draw_action_prompt(x, 715, "F", "빈 병 줍기")
                left, top, width, height = panel.call_args.args
                self.assertTrue(left + width <= x - 28 or left >= x + 28)
                self.assertGreaterEqual(top, 8)
                self.assertLessEqual(left + width, 1280 - 8)
                self.assertLessEqual(top + height, 720 - 8)
        fill.assert_not_called()

    def test_pause_pages_show_navigation_controls_and_selected_volume(self):
        with (patch.object(self.hud, "_text") as text, patch.object(self.hud, "_keycap") as cap,
              patch.object(play_hud, "panel"), patch.object(play_hud, "receipt_rule"),
              patch.object(play_hud, "trace"), patch.object(play_hud, "fill") as fill):
            self.hud.draw_pause("main", 1, (100, 45, 0))
            labels = [call.args for call in text.call_args_list]
            self.assertEqual([entry[0] for entry in labels[1:6]], list(play_hud.PAUSE_MENU))
            self.assertEqual(labels[2][4], play_hud.STAMP)
            text.reset_mock()
            self.hud.draw_pause("controls", 0, (100, 45, 0))
            keys = {call.args[0] for call in cap.call_args_list}
            self.assertTrue({"W", "A", "S", "D", "F", "Q", "M", "E", "Shift", "Ctrl", "Esc", "R", "Space",
                             "1", "2", "3"} <= keys)
            self.assertIn("마우스 조준 · 좌클릭 배트", {call.args[0] for call in text.call_args_list})
            text.reset_mock()
            fill.reset_mock()
            self.hud.draw_pause("audio", 1, (100, 45, 0))
            self.assertTrue({"전체", "음악", "효과음", "100%", "45%", "0%"} <= {
                call.args[0] for call in text.call_args_list})
            self.assertTrue(any(call.args[2:] == (97, 8, (*play_hud.STAMP, 255))
                                for call in fill.call_args_list))

    def test_result_draws_stats_and_retry_releases_dynamic_count_label(self):
        self.world.result = "delivered"
        self.world.attack_count = 123
        with patch.object(self.hud, "_text") as text, patch.object(play_hud, "panel"), patch.object(play_hud, "fill"):
            self.hud.draw_result(self.world)
        labels = {args[0] for args, _ in text.call_args_list}
        self.assertTrue({"배달 성공", "계약", self.world.contract.name, "남은 체력", "3 / 3", "공격 횟수", "123회",
                         "교전 없이 배달", "미달성", "Enter 같은 배송 재도전  ·  R 배달 선택  ·  Esc 종료"} <= labels)
        texture = object()
        key = ("123회", play_hud.BODY, play_hud.TEXT)
        self.hud._labels[key] = (texture, 40, 20)
        with patch.object(play_hud.p, "SDL_DestroyTexture") as destroy:
            self.hud.reset_delivery()
        self.assertNotIn(key, self.hud._labels)
        destroy.assert_called_once_with(texture)

    def test_three_stop_hud_shows_last_target_and_partial_result(self):
        self.world = DeliveryWorld(two_stop_unlocked=True)
        self.assertTrue(self.world.select_contract(2))
        self.assertTrue(self.world.interact())
        shop, rear_door, bus = self.world.contract.stops
        self.world.player.x, self.world.player.y = rear_door.position
        self.assertEqual(self.world.interaction_target, rear_door.position)
        self.assertTrue(self.world.interact())

        with patch.object(self.hud, "_text") as text, patch.object(play_hud, "panel"), patch.object(play_hud, "fill"):
            play_hud.PlayHUD._objective(self.hud, self.world)
            self.assertTrue({"1 / 3", "배송지 선택"} <= {args[0] for args, _ in text.call_args_list})
            self.world.player.x, self.world.player.y = shop.position
            self.assertTrue(self.world.interact())
            text.reset_mock()
            play_hud.PlayHUD._objective(self.hud, self.world)
            self.assertTrue({"2 / 3", bus.name} <= {args[0] for args, _ in text.call_args_list})
            text.reset_mock()
            self.world.player_hp = 0
            self.world.result = "defeated"
            self.hud.draw_result(self.world)
        labels = {args[0] for args, _ in text.call_args_list}
        self.assertTrue({"배달 실패", f"{shop.name} · 완료", f"{rear_door.name} · 완료", f"{bus.name} · 미완료"}
                        <= labels)

    def test_first_success_result_announces_new_contract(self):
        self.assertTrue(self.world.interact())
        for stop in self.world.contract.stops:
            self.world.player.x, self.world.player.y = stop.position
            self.assertTrue(self.world.interact())
        with patch.object(self.hud, "_text") as text, patch.object(play_hud, "panel"), patch.object(play_hud, "fill"):
            self.hud.draw_result(self.world)
        labels = {args[0] for args, _ in text.call_args_list}
        self.assertIn("새 계약 열림 · R에서 3번 선택", labels)

    def test_truck_route_objective_and_receipt_follow_all_deliveries(self):
        self.assertTrue(self.world.select_contract(3))

        def shown_text():
            with (patch.object(self.hud, "_text") as text, patch.object(play_hud, "panel"),
                  patch.object(play_hud, "fill"), patch.object(play_hud, "receipt_rule")):
                if self.world.result == "delivered":
                    self.hud.draw_result(self.world)
                else:
                    play_hud.PlayHUD._objective(self.hud, self.world)
            return {args[0] for args, _ in text.call_args_list}

        self.assertTrue({"트럭 도착 중", "Enter 건너뛰기"} <= shown_text())
        self.assertTrue(self.world.skip_route_sequence())
        self.assertIn("트럭에서 택배 수령", shown_text())
        self.assertTrue(self.world.interact())
        self.assertTrue({"배송지 선택", "0 / 3"} <= shown_text())
        shop, rear, bus = self.world.contract.stops
        self.world.player.x, self.world.player.y = rear.position
        self.assertTrue(self.world.interact())
        self.assertTrue({"배송지 선택", "1 / 3"} <= shown_text())
        self.world.player.x, self.world.player.y = bus.position
        self.assertTrue(self.world.interact())
        self.assertTrue({shop.name, "2 / 3"} <= shown_text())
        self.world.player.x, self.world.player.y = shop.position
        self.assertTrue(self.world.interact())
        self.assertTrue({"트럭으로 복귀", "3 / 3"} <= shown_text())
        self.world.player.x, self.world.player.y = self.world.contract.truck_door_position
        self.assertTrue(self.world.interact())
        self.assertIn("트럭 출차 중", shown_text())
        self.assertTrue(self.world.skip_route_sequence())
        self.assertTrue({"배달 성공", "출차 완료", f"{shop.name} · 완료", f"{rear.name} · 완료", f"{bus.name} · 완료"}
                        <= shown_text())

    def test_waypoint_arrow_uses_screen_direction_and_hides_on_focus_loss(self):
        with (patch.object(play_hud, "panel"), patch.object(play_hud, "trace") as trace,
              patch.object(self.hud, "_text") as text):
            for direction, head in (((10, 0), (8, 0)), ((0, -10), (0, -8)), ((10, 6), (7, 4))):
                self.hud.draw(self.world, self.light, self.world.next_stop, focused=True, alarm=False,
                              waypoint_direction=direction)
                self.assertEqual(trace.call_args.args[2][1], head)
                self.assertEqual(text.call_args.args[0], "경유지 1 방향")
            trace.reset_mock()
            self.hud.draw(self.world, self.light, self.world.next_stop, focused=False, alarm=False,
                          waypoint_direction=(0, -10))
            trace.assert_not_called()
