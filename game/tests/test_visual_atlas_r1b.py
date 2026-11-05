"""R1-B atlas geometry contracts; not a visual animation-quality verdict."""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import struct
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from locomotion import Locomotion, STRIDE_DISTANCE
from player_visual import METADATA_PATH, PlayerVisual


FACINGS = (
    ("front_right", -math.pi / 4),
    ("back_right", math.pi / 4),
    ("back_left", 3 * math.pi / 4),
    ("front_left", -3 * math.pi / 4),
)

# Immutable source records retained from 526c96c before the 64px sheets.
BASELINE_SOURCES = "a2cc4aa080dd68f44581cd0c9071030f5d7f4ab42d0433aa3cd0ab0a2c3d15b0"
PRESERVED_SOURCE_HASHES = {
    "atlas": "ce8c0ac85daa5b7f8aebf44464b858db0bc192d4a838a493f774799690d24981",
    "front_steps": "ee7eaafeb48fdd435079d168d78d115ec20849e6350725a6214c5e95ab5abb75",
    "smooth_front_right": "b788c200ffc000d225cf228769cea01fe5f5bba2ab79ef52ff77cf0012b3d667",
    "smooth_back_right": "201fce1a74c302b0b180d52ab168ed84e6b04bfd5192a6063a00c19041f790af",
    "smooth_back_left": "1b6fb22c7b8e5da37eef6ee89bd0168378aad8653b554bb09a8f43f455728558",
    "smooth_front_left": "d3dcd3d3ff13be1eb03c3c07d27087ace3824535ec592dacb7bfbf625958b5f1",
    "weight_front_right": "d0330535d62b4586315aa373df9f12538a7e125b6e534eb61b16f5a171af57c6",
    "landing_front_right": "27dcbfb0004dc06943cb15a7dc3f279167ee84002d6ff066235949da7ee562d8",
    "alternating_front_right": "ff65046d6e4d0ed99813a2cb778074f5ea8ddcd41d51e95af4c1eb00da5dc602",
    "unified_front_right": "c050077ad86918868739ec2a7688ba8a6cc4d46f84da51fe2c7802caac1cd7d5",
    "unified_back_right": "fe19c109da30a9ab61f8564356a44befea21329459c936c3340461c4467c3972",
    "unified_back_left": "f3193c8689efd0bb36ca056f678253fdca3f72d2c6af883c82e165423eb58ff6",
    "unified_front_left": "a19acd5b697b954394997099717adbea1db29b0fbfc96a99604dd2cbe5f7459c",
}
ACTIVE_SOURCES = {facing: "pixel64_" + facing for facing, _ in FACINGS}


def canonical_hash(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


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

    def frame_steps(self, facing):
        count = len(self.metadata["frames"][facing]) - 1
        return [0.0, STRIDE_DISTANCE / (2 * count)] + [STRIDE_DISTANCE / count] * (count - 1)

    def test_frames_fit_sources_and_preserve_earlier_art(self):
        metadata = self.metadata
        self.assertEqual(set(metadata["frames"]), {name for name, _ in FACINGS})
        self.assertEqual(metadata["display_height"], 128)
        self.assertEqual(metadata["sampling"], "nearest")
        sources = metadata["sources"]
        self.assertEqual(set(sources), set(PRESERVED_SOURCE_HASHES) | set(ACTIVE_SOURCES.values()))
        self.assertEqual(canonical_hash({name: sources[name] for name in PRESERVED_SOURCE_HASHES}),
                         BASELINE_SOURCES)
        self.assertEqual(metadata["image"], sources["atlas"]["image"])
        self.assertEqual(metadata["canvas_size"], sources["atlas"]["canvas_size"])
        self.assertEqual(len({sources[name]["sha256"] for name in ACTIVE_SOURCES.values()}), 4)
        for source, entry in sources.items():
            with self.subTest(source=source):
                image_path = METADATA_PATH.parent / entry["image"]
                header = image_path.read_bytes()[:24]
                self.assertEqual(header[:8], b"\x89PNG\r\n\x1a\n")
                self.assertEqual(tuple(entry["canvas_size"]), struct.unpack(">II", header[16:24]))
                digest = hashlib.sha256(image_path.read_bytes()).hexdigest()
                expected = PRESERVED_SOURCE_HASHES.get(source, entry.get("sha256", "").lower())
                self.assertEqual(digest, expected)

        for facing, _ in FACINGS:
            source = ACTIVE_SOURCES[facing]
            source_info = sources[source]
            self.assertEqual(source_info["canvas_size"], [320, 240])
            self.assertEqual(source_info["scale_reference_height"], 64)
            self.assertEqual(source_info["cell_local_body_root"], [40, 72])
            grid = source_info["grid"]
            self.assertEqual((grid["columns"], grid["rows"]), (4, 3))
            self.assertEqual(grid["cell_boundaries_x"], [0, 80, 160, 240, 320])
            self.assertEqual(grid["cell_boundaries_y"], [0, 80, 160, 240])
            frames = metadata["frames"][facing]
            self.assertEqual(len(frames), 9)
            self.assertEqual(frames[0]["name"], "idle")
            seen = set()
            for index, frame in enumerate(frames):
                with self.subTest(facing=facing, frame=index):
                    self.assertEqual(frame["source"], source)
                    slot = index - 1 if index else 8
                    cell_left, cell_top = (slot % 4) * 80, (slot // 4) * 80
                    self.assertEqual(frame["cell_topleft"], [cell_left, cell_top, 80, 80])
                    self.assertEqual(frame["foot_pivot_topleft"], [cell_left + 40, cell_top + 72])
                    self.assertEqual(frame["scale_reference_height"], 64)
                    left, top, width, height = frame["clip_topleft"]
                    self.assertTrue(all(isinstance(value, int) for value in (left, top, width, height)))
                    self.assertGreater(width, 0)
                    self.assertGreater(height, 0)
                    self.assertGreaterEqual(left, cell_left)
                    self.assertGreaterEqual(top, cell_top)
                    self.assertLessEqual(left + width, cell_left + 80)
                    self.assertLessEqual(top + height, cell_top + 80)
                    seen.add(tuple(frame["clip_topleft"]))
                    if index:
                        self.assertAlmostEqual(frame["phase"], (index - 1) / 8)
            self.assertEqual(len(seen), 9)
        idle = metadata["frames"]["front_right"][0]
        self.assertEqual(metadata["clip_topleft"], idle["clip_topleft"])
        self.assertEqual(metadata["foot_pivot_topleft"], idle["foot_pivot_topleft"])

    def test_real_locomotion_selects_all_frames_and_draw_keeps_ground_anchor(self):
        foot = (640.125, 271.5)
        for facing, angle in FACINGS:
            visual = self.make_visual()
            for index, displacement in enumerate(self.frame_steps(facing)):
                with self.subTest(facing=facing, frame=index):
                    visual.update(angle, displacement, 0.0)
                    self.assertEqual(visual.locomotion.facing, facing)
                    self.assertEqual(visual.frame_index, index)
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

    def test_idle_and_walk_keep_the_same_fixed_scale_reference(self):
        for facing, angle in FACINGS:
            for index in range(9):
                with self.subTest(facing=facing, frame=index):
                    metadata = deepcopy(self.metadata)
                    frame = metadata["frames"][facing][index]
                    visual = self.make_visual(metadata)
                    distance = (index - 0.5) * STRIDE_DISTANCE / 8 if index else 0.0
                    visual.update(angle, distance, 0.0)
                    self.assertEqual(visual.frame_index, index)
                    arguments = self.draw_arguments(visual, frame, (500.0, 300.0))
                    scale = metadata["display_height"] / frame["scale_reference_height"]
                    self.assertEqual(scale, 2)
                    self.assertAlmostEqual(arguments[6], frame["clip_topleft"][2] * scale, places=9)
                    self.assertAlmostEqual(arguments[7], frame["clip_topleft"][3] * scale, places=9)
                    # Clipping less of a pose must not normalize it to a new scale.
                    frame["clip_topleft"][3] = max(1, frame["clip_topleft"][3] // 2)
                    changed_height = self.draw_arguments(visual, frame, (500.0, 300.0))[7]
                    self.assertAlmostEqual(changed_height / frame["clip_topleft"][3], scale, places=9)

    def test_draw_translation_preserves_size_state_and_metadata(self):
        for facing, angle, index in (("front_right", -math.pi / 4, 4),
                                     ("back_right", math.pi / 4, 4),
                                     ("back_left", 3 * math.pi / 4, 1),
                                     ("front_left", -3 * math.pi / 4, 2)):
            with self.subTest(facing=facing, frame=index):
                metadata = deepcopy(self.metadata)
                visual = self.make_visual(metadata)
                count = len(metadata["frames"][facing]) - 1
                visual.update(angle, (index - 0.5) * STRIDE_DISTANCE / count, 0.0)
                before_state, before_metadata = asdict(visual.locomotion), deepcopy(metadata)
                frame = metadata["frames"][facing][index]
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
