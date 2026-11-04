"""R1-B atlas geometry contracts; not a visual animation-quality verdict."""
from copy import deepcopy
from dataclasses import asdict
import json
import math
from pathlib import Path
import struct
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from locomotion import Locomotion
from player_visual import METADATA_PATH, PlayerVisual


FACINGS = (
    ("front_right", -math.pi / 4),
    ("back_right", math.pi / 4),
    ("back_left", 3 * math.pi / 4),
    ("front_left", -3 * math.pi / 4),
)


class AtlasGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))

    def make_visual(self, metadata=None):
        # Use real update/draw with a recording image, without initializing SDL.
        visual = PlayerVisual.__new__(PlayerVisual)
        visual.metadata = self.metadata if metadata is None else metadata
        visual.locomotion = Locomotion()
        visual.images = {
            source: SimpleNamespace(w=entry["canvas_size"][0],
                                    h=entry["canvas_size"][1], clip_draw=Mock())
            for source, entry in visual.metadata["sources"].items()
        }
        visual.image = visual.images["atlas"]
        return visual

    def draw_arguments(self, visual, frame, foot):
        for image in visual.images.values():
            image.clip_draw.reset_mock()
        visual.draw(*foot)
        selected = frame.get("source", "atlas")
        for source, image in visual.images.items():
            if source == selected:
                image.clip_draw.assert_called_once()
            else:
                image.clip_draw.assert_not_called()
        return visual.images[selected].clip_draw.call_args.args

    def test_twelve_frames_fit_their_cells_and_base_matches_front_right_idle(self):
        metadata = self.metadata
        self.assertEqual(set(metadata["frames"]), {name for name, _ in FACINGS})
        self.assertEqual(metadata["display_height"], 128)
        self.assertEqual(metadata["sampling"], "nearest")
        sources = metadata["sources"]
        self.assertEqual(set(sources), {"atlas", "front_steps"})
        self.assertEqual(metadata["image"], sources["atlas"]["image"])
        self.assertEqual(metadata["canvas_size"], sources["atlas"]["canvas_size"])
        for source, entry in sources.items():
            with self.subTest(source=source):
                with (METADATA_PATH.parent / entry["image"]).open("rb") as image:
                    header = image.read(24)
                self.assertEqual(header[:8], b"\x89PNG\r\n\x1a\n")
                self.assertEqual(tuple(entry["canvas_size"]), struct.unpack(">II", header[16:24]))
        atlas_count = 0
        corrected_cells = []

        for row, (facing, _) in enumerate(FACINGS):
            frames = metadata["frames"][facing]
            self.assertEqual(len(frames), 3, facing)
            for column, frame in enumerate(frames):
                with self.subTest(facing=facing, frame=column):
                    source = frame.get("source", "atlas")
                    self.assertIn(source, sources)
                    canvas_width, canvas_height = sources[source]["canvas_size"]
                    left, top, width, height = frame["clip_topleft"]
                    self.assertTrue(all(isinstance(value, int)
                                        for value in (left, top, width, height)))
                    self.assertGreater(width, 0)
                    self.assertGreater(height, 0)
                    cell_left, cell_top, cell_width, cell_height = frame["cell_topleft"]
                    self.assertTrue(all(isinstance(value, int) for value in frame["cell_topleft"]))
                    self.assertGreater(cell_width, 0)
                    self.assertGreater(cell_height, 0)
                    cell_right, cell_bottom = cell_left + cell_width, cell_top + cell_height
                    self.assertGreaterEqual(cell_left, 0)
                    self.assertGreaterEqual(cell_top, 0)
                    self.assertLessEqual(cell_right, canvas_width)
                    self.assertLessEqual(cell_bottom, canvas_height)
                    if source == "atlas":
                        atlas_count += 1
                        self.assertEqual((cell_left, cell_top, cell_right, cell_bottom),
                                         (column * canvas_width // 3, row * canvas_height // 4,
                                          (column + 1) * canvas_width // 3,
                                          (row + 1) * canvas_height // 4))
                    else:
                        self.assertEqual(source, "front_steps")
                        self.assertIn(facing, ("front_right", "front_left"))
                        self.assertIn(column, (1, 2))
                        reference = frame["scale_reference_height"]
                        self.assertTrue(math.isfinite(reference))
                        self.assertGreater(reference, 0)
                        corrected_cells.append((cell_left, cell_right))
                    self.assertGreaterEqual(left, cell_left)
                    self.assertLessEqual(left + width, cell_right)
                    self.assertGreaterEqual(top, cell_top)
                    self.assertLessEqual(top + height, cell_bottom)
                    pivot_x, pivot_y = frame["foot_pivot_topleft"]
                    self.assertGreaterEqual(pivot_x, cell_left)
                    self.assertLessEqual(pivot_x, cell_right)
                    self.assertGreaterEqual(pivot_y, cell_top)
                    self.assertLessEqual(pivot_y, cell_bottom)

        self.assertEqual(atlas_count, 10)
        self.assertEqual(len(corrected_cells), 2)
        corrected_cells.sort()
        self.assertLessEqual(corrected_cells[0][1], corrected_cells[1][0])
        idle = metadata["frames"]["front_right"][0]
        self.assertEqual(metadata["clip_topleft"], idle["clip_topleft"])
        self.assertEqual(metadata["foot_pivot_topleft"], idle["foot_pivot_topleft"])

    def test_real_locomotion_selects_all_frames_and_draw_keeps_ground_anchor(self):
        foot = (640.125, 271.5)
        for facing, angle in FACINGS:
            visual = self.make_visual()
            for index, displacement in enumerate((0.0, 8.0, 16.0)):
                with self.subTest(facing=facing, frame=index):
                    visual.update(angle, displacement, 0.0)
                    self.assertEqual(visual.locomotion.facing, facing)
                    self.assertEqual(visual.locomotion.frame_index, index)
                    frame = self.metadata["frames"][facing][index]
                    source_x, source_bottom, source_width, source_height, x, y, width, height = (
                        self.draw_arguments(visual, frame, foot))
                    clip = frame["clip_topleft"]
                    image_height = self.metadata["sources"][frame.get("source", "atlas")]["canvas_size"][1]
                    self.assertEqual(
                        (source_x, source_bottom, source_width, source_height),
                        (clip[0], image_height - clip[1] - clip[3],
                         clip[2], clip[3]))
                    pivot_x, pivot_y = frame["foot_pivot_topleft"]
                    anchor_x = x - width / 2 + width * (pivot_x - clip[0]) / clip[2]
                    anchor_y = y - height / 2 + height * (clip[1] + clip[3] - pivot_y) / clip[3]
                    self.assertAlmostEqual(anchor_x, foot[0], places=9)
                    self.assertAlmostEqual(anchor_y, foot[1], places=9)

    def test_idle_is_128px_and_frames_keep_their_fixed_scale_reference(self):
        atlas_walks, corrected = [], []
        for facing, angle in FACINGS:
            visual = self.make_visual()
            idle_scale = None
            for index, displacement in enumerate((0.0, 8.0, 16.0)):
                with self.subTest(facing=facing, frame=index):
                    visual.update(angle, displacement, 0.0)
                    frame = self.metadata["frames"][facing][index]
                    _, _, source_width, source_height, _, _, width, height = (
                        self.draw_arguments(visual, frame, (500.0, 300.0)))
                    if index == 0:
                        self.assertAlmostEqual(height, 128.0, places=9)
                        idle_scale = height / source_height
                    if frame.get("source", "atlas") == "atlas":
                        self.assertAlmostEqual(height / source_height, idle_scale, places=9)
                        self.assertAlmostEqual(width / source_width, idle_scale, places=9)
                        if index:
                            atlas_walks.append((facing, angle, index))
                    else:
                        self.assertGreater(frame["scale_reference_height"], 0)
                        reference_scale = 128.0 / frame["scale_reference_height"]
                        self.assertAlmostEqual(height / source_height, reference_scale, places=9)
                        self.assertAlmostEqual(width / source_width, reference_scale, places=9)
                        corrected.append((facing, angle, index))

        self.assertTrue(atlas_walks)
        self.assertEqual(len(corrected), 2)
        # Changing a frame's box must preserve its fixed reference, not normalize
        # that frame's height to 128. Exercise both the original and added source.
        for facing, angle, index in atlas_walks[:1] + corrected:
            varied = deepcopy(self.metadata)
            frame = varied["frames"][facing][index]
            visual = self.make_visual(varied)
            visual.update(angle, 8.0 if index == 1 else 24.0, 0.0)
            original_height = self.draw_arguments(visual, frame, (500.0, 300.0))[7]
            source_height = frame["clip_topleft"][3]
            frame["clip_topleft"][3] = max(1, source_height // 2)
            changed_height = self.draw_arguments(visual, frame, (500.0, 300.0))[7]
            self.assertAlmostEqual(changed_height / frame["clip_topleft"][3],
                                   original_height / source_height, places=9)

    def test_draw_translation_preserves_size_state_and_metadata(self):
        metadata = deepcopy(self.metadata)
        visual = self.make_visual(metadata)
        visual.update(3 * math.pi / 4, 8.0, 0.0)
        before_state, before_metadata = asdict(visual.locomotion), deepcopy(metadata)
        frame = metadata["frames"]["back_left"][1]
        first = self.draw_arguments(visual, frame, (400.0, 250.0))
        second = self.draw_arguments(visual, frame, (511.25, 219.5))
        self.assertEqual(first[:4], second[:4])
        self.assertAlmostEqual(second[4] - first[4], 111.25, places=9)
        self.assertAlmostEqual(second[5] - first[5], -30.5, places=9)
        self.assertEqual(first[6:], second[6:])
        self.assertEqual(asdict(visual.locomotion), before_state)
        self.assertEqual(metadata, before_metadata)


if __name__ == "__main__":
    unittest.main()
