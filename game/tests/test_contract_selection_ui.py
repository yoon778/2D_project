"""Shared contract card hitboxes and dispatch-sheet rendering."""
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import contract_selection as selection
from delivery import PLAYABLE_CONTRACTS


class ContractSelectionTests(unittest.TestCase):
    def test_cards_dispatch_and_gaps_use_the_same_screen_rectangles(self):
        self.assertEqual(len(selection.CARD_RECTS), 4)
        for index, (left, top, width, height) in enumerate(selection.CARD_RECTS):
            self.assertEqual(selection.contract_card_at(left, top), index)
            self.assertEqual(selection.contract_card_at(left + width - 1, top + height - 1), index)
            self.assertIsNone(selection.contract_card_at(left + width, top))
            self.assertIsNone(selection.contract_card_at(left, top + height))
        self.assertTrue(selection.contract_dispatch_at(220, 557))
        self.assertIsNone(selection.contract_card_at(220, 557))
        self.assertFalse(selection.contract_dispatch_at(220, 600))

    def test_four_route_cards_use_stable_numbers_and_matching_photo_and_stops(self):
        contracts = tuple(PLAYABLE_CONTRACTS.values())
        hud = Mock(width=1280, height=720)
        images = [Mock() for _ in contracts]
        route, pin = Mock(), Mock()
        with (patch.object(selection, "fill"), patch.object(selection, "panel"),
              patch.object(selection, "receipt_rule")):
            selection.draw_contract_selection(hud, contracts, contracts,
                                              2, (220, 557), images, route, pin)
        selected = contracts[2]
        shown = {call.args[0] for call in hud._text.call_args_list}
        self.assertIn("1·2·3·4 선택   ·   Esc 종료", shown)
        self.assertIn("출발", shown)
        self.assertNotIn("계약 잠김", shown)
        self.assertTrue({"1", "2", "3", "4", "남쪽 출입구로 들어가 보급실에 배달"} <= shown)
        self.assertNotIn("순서 자유", shown)
        self.assertEqual(selected.number, 3)
        self.assertTrue({stop.name for stop in selected.stops} <= shown)
        images[2].draw_to_origin.assert_called_once()
        self.assertEqual(sum(image.draw_to_origin.call_count for image in images), 1)
        self.assertEqual(pin.call_count, len(selected.stops) + 1)  # Includes the return truck.
        route.assert_called_once_with(selected, (478, 425, 382, 247))
