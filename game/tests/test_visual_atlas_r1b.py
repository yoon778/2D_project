"""R1-C8-WALK 아틀라스 기하·기존 원화 보존 검사. 주관적 보행 품질과 구분한다."""
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
    ("front", -math.pi / 2),
    ("back", math.pi / 2),
    ("left", math.pi),
    ("right", 0.0),
)

# b665762의 기존21소스와 PNG 기록은 고정하며 active8방향은 이번 교체 대상이다.
BASELINE_SOURCES = '51d9287ae98ae2f14b80acee59078b58a1b072d9f81dfcab241485a1e7cb32fc'
BASELINE_LEGACY_TOP_VALUES = '40bbad8f0fc0cf14826fbc07b0064b0d5b72d347f9f036ccbb37ba66bd0f5325'
APPROVED_IDLE_MASTER_SHA256 = '45ddbc25c2e4a3afa9435f973bc6e944374755b3bb2f101ec52612c2e690fdad'
PRESERVED_SOURCE_HASHES = {
    "atlas": "CE8C0AC85DAA5B7F8AEBF44464B858DB0BC192D4A838A493F774799690D24981",
    "front_steps": "EE7EAAFEB48FDD435079D168D78D115EC20849E6350725A6214C5E95AB5ABB75",
    "smooth_front_right": "B788C200FFC000D225CF228769CEA01FE5F5BBA2AB79EF52FF77CF0012B3D667",
    "smooth_back_right": "201FCE1A74C302B0B180D52AB168ED84E6B04BFD5192A6063A00C19041F790AF",
    "smooth_back_left": "1B6FB22C7B8E5DA37EEF6EE89BD0168378AAD8653B554BB09A8F43F455728558",
    "smooth_front_left": "D3DCD3D3FF13BE1EB03C3C07D27087ACE3824535EC592DACB7BFBF625958B5F1",
    "weight_front_right": "D0330535D62B4586315AA373DF9F12538A7E125B6E534EB61B16F5A171AF57C6",
    "landing_front_right": "27DCBFB0004DC06943CB15A7DC3F279167EE84002D6FF066235949DA7EE562D8",
    "alternating_front_right": "ff65046d6e4d0ed99813a2cb778074f5ea8ddcd41d51e95af4c1eb00da5dc602",
    "unified_front_right": "c050077ad86918868739ec2a7688ba8a6cc4d46f84da51fe2c7802caac1cd7d5",
    "unified_back_right": "fe19c109da30a9ab61f8564356a44befea21329459c936c3340461c4467c3972",
    "unified_back_left": "f3193c8689efd0bb36ca056f678253fdca3f72d2c6af883c82e165423eb58ff6",
    "unified_front_left": "a19acd5b697b954394997099717adbea1db29b0fbfc96a99604dd2cbe5f7459c",
    "pixel64_front_right": "7956778dee5244e6f19a9cd917db1e885d13dbdc5b1c61a3ce09961787340806",
    "pixel64_back_right": "f49c7eca2427904e88ae462e79dc3d4ff1154f7226f192605f5abb74af292f3d",
    "pixel64_back_left": "5007e221e59c50a61220263fff4b3ff73afa8eb2b7708d887dbd9fbf472fdbb9",
    "pixel64_front_left": "2d8fb57347c3ac8b3431970d9d4f8217909684a5484d5fff6ef71b70b1d3bc09",
    "pixel64_front": "657ff560a9d9d0ea0a2555d6013b607bc19283d27ec7ae35bddf75f91b39fc33",
    "pixel64_back": "ceaf6865ad867d693e1e82050e21ceac54bf0af6ff2c828f08182b991682a177",
    "pixel64_left": "c5b05cb58ef9cbe17297572cce0ed93decfd8c4e0385a65b1668aee6ec15f859",
    "pixel64_right": "5568ea2c567ba57dd7ff8dc277fbd137c360423dba4517a6813966f5081f155e"
}
PRESERVED_EXTRA_PNG_HASHES = {
    "r1a-courier-20261104.png": "a928d8df6fdafad919af79e59b4ad805afbbf07b2cc2a4e11c98c8bc23b83539"
}
ACTIVE_SOURCES = {facing: "consistent_" + facing for facing, _ in FACINGS}


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
        legacy = {key: value for key, value in metadata.items()
                  if key not in ("sources", "frames", "edited_on", "review_status", "sprint")}
        self.assertEqual(canonical_hash(legacy), BASELINE_LEGACY_TOP_VALUES)
        master = METADATA_PATH.parents[3] / "art/player/style-studies/eight-direction-consistency/turnaround-idle-64-v3.png"
        self.assertEqual(hashlib.sha256(master.read_bytes()).hexdigest(), APPROVED_IDLE_MASTER_SHA256)
        for name, expected in PRESERVED_EXTRA_PNG_HASHES.items():
            self.assertEqual(hashlib.sha256((METADATA_PATH.parent / name).read_bytes()).hexdigest(), expected)
        self.assertEqual(sum(len(frames) for frames in metadata["frames"].values()), 72)
        self.assertEqual(metadata["image"], sources["atlas"]["image"])
        self.assertEqual(metadata["canvas_size"], sources["atlas"]["canvas_size"])
        self.assertEqual(len({sources[name]["sha256"] for name in ACTIVE_SOURCES.values()}), 8)
        for source, entry in sources.items():
            with self.subTest(source=source):
                image_path = METADATA_PATH.parent / entry["image"]
                header = image_path.read_bytes()[:24]
                self.assertEqual(header[:8], b"\x89PNG\r\n\x1a\n")
                self.assertEqual(tuple(entry["canvas_size"]), struct.unpack(">II", header[16:24]))
                digest = hashlib.sha256(image_path.read_bytes()).hexdigest()
                expected = PRESERVED_SOURCE_HASHES.get(source, entry.get("sha256", "")).lower()
                self.assertEqual(digest, expected)

        for facing, _ in FACINGS:
            source = ACTIVE_SOURCES[facing]
            source_info = sources[source]
            self.assertEqual(source_info["canvas_size"], [320, 240])
            self.assertEqual(source_info["scale_reference_height"], 64)
            self.assertEqual(source_info["cell_local_body_root"], [40, 72])
            self.assertEqual(source_info["provenance"]["master_sha256"], APPROVED_IDLE_MASTER_SHA256)
            self.assertEqual(source_info["alpha_values"], [0, 255])
            self.assertLessEqual(source_info["visible_color_count"], 24)
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

    def test_real_locomotion_selects_all_frames_and_draw_keeps_ground_anchor(self):
        foot = (640.125, 271.5)
        for facing, angle in FACINGS:
            visual = self.make_visual()
            for index, displacement in enumerate(self.frame_steps(facing)):
                with self.subTest(facing=facing, frame=index):
                    visual.update(angle, displacement * math.cos(angle), displacement * math.sin(angle))
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
                    visual.update(angle, distance * math.cos(angle), distance * math.sin(angle))
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

    def test_sprint_preserves_walk_phase_and_selects_both_atlases(self):
        visual = self.make_visual()
        visual.display_scale = 0.75
        visual.images["sprint"] = SimpleNamespace(h=160, clip_draw=Mock())
        visual.empty_images = {"sprint": SimpleNamespace(h=160, clip_draw=Mock())}
        angle = -math.pi / 4

        visual.update(angle, 8 / math.sqrt(2), -8 / math.sqrt(2))
        self.assertEqual(visual.frame_index, 2)
        visual.update(angle, 12 / math.sqrt(2), -12 / math.sqrt(2), sprinting=True)
        self.assertTrue(visual.sprinting)
        self.assertAlmostEqual(visual.locomotion.phase, 0.25)
        self.assertEqual(visual.frame_index, 3)
        for key, empty in (("images", False), ("empty_images", True)):
            visual.draw(500, 300, empty_handed=empty)
            getattr(visual, key)["sprint"].clip_draw.assert_called_once_with(
                160, 80, 80, 80, 500, 348, 120, 120)

        visual.update(angle, 8 / math.sqrt(2), -8 / math.sqrt(2))
        self.assertFalse(visual.sprinting)
        self.assertAlmostEqual(visual.locomotion.phase, 0.375)
        self.assertEqual(visual.frame_index, 4)
        visual.update(angle, 1e-7, -1e-7, sprinting=True)
        self.assertFalse(visual.sprinting)
        self.assertEqual(visual.frame_index, 0)

    def test_draw_translation_preserves_size_state_and_metadata(self):
        for facing, angle, index in (("front_right", -math.pi / 4, 4),
                                     ("back_right", math.pi / 4, 4),
                                     ("back_left", 3 * math.pi / 4, 1),
                                     ("front_left", -3 * math.pi / 4, 2),
                                     ("front", -math.pi / 2, 4),
                                     ("back", math.pi / 2, 4),
                                     ("left", math.pi, 4),
                                     ("right", 0.0, 4)):
            with self.subTest(facing=facing, frame=index):
                metadata = deepcopy(self.metadata)
                visual = self.make_visual(metadata)
                count = len(metadata["frames"][facing]) - 1
                distance = (index - 0.5) * STRIDE_DISTANCE / count
                visual.update(angle, distance * math.cos(angle), distance * math.sin(angle))
                self.assertEqual(visual.frame_index, index)
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
