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

LEGACY_SOURCE_HASHES = {
    "atlas": "ce8c0ac85daa5b7f8aebf44464b858db0bc192d4a838a493f774799690d24981",
    "front_steps": "ee7eaafeb48fdd435079d168d78d115ec20849e6350725a6214c5e95ab5abb75",
    "smooth_front_right": "b788c200ffc000d225cf228769cea01fe5f5bba2ab79ef52ff77cf0012b3d667",
}
# Canonical JSON hashes from git show 358978f, not from the changing live JSON.
BASELINE_FRONT_RIGHT = "fffd766f9f9ae6dbb22caa6457ec32b9ae39c0aed8de6a53a47d96cf4edae711"
BASELINE_IDLES = "56584c6445ae8a552a90aa67c20133578909816e7ba78566094232bf7eee0a16"
BASELINE_SOURCES = "da1f838de0f2f309fc083e8b1e2d499c472590a0112079044f0dac4e783f93b6"
# Preserve the approved BR stage exactly from git show 9b6bb29.
BASELINE_BACK_RIGHT_FRAMES = "388e9b486e1cb9f50a620ad2c91a4187db409f749cab0faeab2311b51eed6997"
BASELINE_BACK_RIGHT_SOURCE = "534a1fc147b2a62cd97d8446d53c2a25e8aca42e5ba2631dbaf148d891d0ddf3"
BASELINE_BACK_RIGHT_PNG = "201fce1a74c302b0b180d52ab168ed84e6b04bfd5192a6063a00c19041f790af"
BASELINE_WAITING_FRAMES = {
    "back_right": "c82dc04a7caaf54061a04524d31249efd45f03ec47276ff7965295ddd26b12c3",
    "back_left": "955ec71b95f265b40439d066b35e026a322be88a6ae966a0788f1b1374072a8d",
    "front_left": "bd48db6087261dfff86233107bbd0d292a6acfcaf5314b70458e2cfaee183693",
}
SMOOTH_SOURCES = {facing: "smooth_" + facing for facing, _ in FACINGS}
S2_ORDER = ("back_right", "back_left", "front_left")


def canonical_hash(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


LEGACY_FRAMES = {
    "back_right": [
        ("atlas", [98, 389, 190, 313], [182, 694], None),
        ("atlas", [462, 389, 189, 303], [544, 694], None),
        ("atlas", [824, 389, 189, 314], [906, 694], None),
    ],
    "back_left": [
        ("atlas", [95, 752, 188, 311], [189, 1054], None),
        ("atlas", [458, 752, 188, 312], [551, 1054], None),
        ("atlas", [821, 752, 186, 311], [913, 1054], None),
    ],
    "front_left": [
        ("atlas", [83, 1114, 186, 306], [180, 1412], None),
        ("atlas", [440, 1115, 191, 306], [542, 1412], None),
        ("front_steps", [1096, 104, 418, 716], [1312, 749], 665.127547),
    ],
}


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

    def expanded_facings(self):
        return {facing for facing, source in SMOOTH_SOURCES.items()
                if source in self.metadata["sources"]}

    def test_staged_frames_fit_sources_and_preserve_baseline(self):
        metadata = self.metadata
        self.assertEqual(set(metadata["frames"]), {name for name, _ in FACINGS})
        self.assertEqual(metadata["display_height"], 128)
        self.assertEqual(metadata["sampling"], "nearest")
        sources = metadata["sources"]
        expanded = self.expanded_facings()
        self.assertEqual(expanded, {"front_right", "back_right", "back_left"})
        progress = [facing for facing in S2_ORDER if facing in expanded]
        self.assertEqual(progress, list(S2_ORDER[:len(progress)]))
        self.assertEqual(set(sources), set(LEGACY_SOURCE_HASHES) |
                         {SMOOTH_SOURCES[facing] for facing in progress})
        self.assertEqual(canonical_hash(metadata["frames"]["front_right"]), BASELINE_FRONT_RIGHT)
        self.assertEqual(canonical_hash({name: frames[0] for name, frames in metadata["frames"].items()}),
                         BASELINE_IDLES)
        self.assertEqual(canonical_hash({name: sources[name] for name in LEGACY_SOURCE_HASHES}),
                         BASELINE_SOURCES)
        self.assertEqual(canonical_hash(metadata["frames"]["back_right"]), BASELINE_BACK_RIGHT_FRAMES)
        self.assertEqual(canonical_hash(sources["smooth_back_right"]), BASELINE_BACK_RIGHT_SOURCE)
        self.assertEqual(metadata["image"], sources["atlas"]["image"])
        self.assertEqual(metadata["canvas_size"], sources["atlas"]["canvas_size"])
        pinned_source_hashes = {**LEGACY_SOURCE_HASHES, "smooth_back_right": BASELINE_BACK_RIGHT_PNG}
        for source, entry in sources.items():
            with self.subTest(source=source):
                with (METADATA_PATH.parent / entry["image"]).open("rb") as image:
                    header = image.read(24)
                self.assertEqual(header[:8], b"\x89PNG\r\n\x1a\n")
                self.assertEqual(tuple(entry["canvas_size"]), struct.unpack(">II", header[16:24]))
                if source in pinned_source_hashes:
                    self.assertEqual(hashlib.sha256(
                        (METADATA_PATH.parent / entry["image"]).read_bytes()).hexdigest(),
                        pinned_source_hashes[source])
                else:
                    self.assertEqual(hashlib.sha256(
                        (METADATA_PATH.parent / entry["image"]).read_bytes()).hexdigest(),
                        entry["sha256"].lower())
        counts = {source: 0 for source in sources}
        smooth_references = {facing: [] for facing in expanded}

        for row, (facing, _) in enumerate(FACINGS):
            frames = metadata["frames"][facing]
            self.assertEqual(len(frames), 9 if facing in expanded else 3, facing)
            if facing not in expanded:
                self.assertEqual(canonical_hash(frames), BASELINE_WAITING_FRAMES[facing])
                self.assertEqual([
                    (frame.get("source", "atlas"), frame["clip_topleft"],
                     frame["foot_pivot_topleft"], frame.get("scale_reference_height"))
                    for frame in frames], LEGACY_FRAMES[facing])
            for column, frame in enumerate(frames):
                with self.subTest(facing=facing, frame=column):
                    source = frame.get("source", "atlas")
                    self.assertIn(source, sources)
                    counts[source] += 1
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
                        self.assertEqual((cell_left, cell_top, cell_right, cell_bottom),
                                         (column * canvas_width // 3, row * canvas_height // 4,
                                          (column + 1) * canvas_width // 3,
                                          (row + 1) * canvas_height // 4))
                    elif source == "front_steps":
                        self.assertEqual((facing, column), ("front_left", 2))
                        reference = frame["scale_reference_height"]
                        self.assertTrue(math.isfinite(reference))
                        self.assertGreater(reference, 0)
                        self.assertEqual((cell_left, cell_top, cell_width, cell_height),
                                         (887, 0, 887, 887))
                    else:
                        self.assertIn(facing, expanded)
                        self.assertEqual(source, SMOOTH_SOURCES[facing])
                        self.assertIn(column, range(1, 9))
                        smooth_column, smooth_row = (column - 1) % 4, (column - 1) // 4
                        grid = sources[source]["grid"]
                        self.assertEqual((grid["columns"], grid["rows"]), (4, 2))
                        boundaries_x, boundaries_y = grid["cell_boundaries_x"], grid["cell_boundaries_y"]
                        self.assertEqual(boundaries_x, [index * canvas_width // 4 for index in range(5)])
                        self.assertEqual(boundaries_y, [index * canvas_height // 2 for index in range(3)])
                        self.assertEqual((cell_left, cell_top, cell_right, cell_bottom),
                                         (boundaries_x[smooth_column], boundaries_y[smooth_row],
                                          boundaries_x[smooth_column + 1], boundaries_y[smooth_row + 1]))
                        reference = frame["scale_reference_height"]
                        self.assertTrue(math.isfinite(reference))
                        self.assertGreater(reference, 0)
                        self.assertEqual(reference, sources[source]["scale_reference_height"])
                        root_x, root_y = sources[source]["cell_local_body_root"]
                        pivot_x, pivot_y = frame["foot_pivot_topleft"]
                        self.assertAlmostEqual(pivot_x - cell_left, root_x, places=6)
                        self.assertAlmostEqual(pivot_y - cell_top, root_y, places=6)
                        smooth_references[facing].append(reference)
                    self.assertGreaterEqual(left, cell_left)
                    self.assertLessEqual(left + width, cell_right)
                    self.assertGreaterEqual(top, cell_top)
                    self.assertLessEqual(top + height, cell_bottom)
                    pivot_x, pivot_y = frame["foot_pivot_topleft"]
                    self.assertGreaterEqual(pivot_x, cell_left)
                    self.assertLessEqual(pivot_x, cell_right)
                    self.assertGreaterEqual(pivot_y, cell_top)
                    self.assertLessEqual(pivot_y, cell_bottom)

        expected_counts = {source: 0 for source in sources}
        for facing, _ in FACINGS:
            expected_counts["atlas"] += 1
            if facing in expanded:
                expected_counts[SMOOTH_SOURCES[facing]] += 8
            else:
                for source, _, _, _ in LEGACY_FRAMES[facing][1:]:
                    expected_counts[source] += 1
        self.assertEqual(counts, expected_counts)
        for facing, references in smooth_references.items():
            with self.subTest(common_scale=facing):
                self.assertEqual(len(references), 8)
                self.assertTrue(all(reference == references[0] for reference in references))
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

    def test_idle_is_128px_and_frames_keep_their_fixed_scale_reference(self):
        atlas_walks, overrides = [], []
        for facing, angle in FACINGS:
            visual = self.make_visual()
            idle_scale = None
            for index, displacement in enumerate(self.frame_steps(facing)):
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
                        overrides.append((facing, angle, index))

        self.assertTrue(overrides)
        expected_overrides = 8 * len(self.expanded_facings()) + ("front_left" not in self.expanded_facings())
        self.assertEqual(len(overrides), expected_overrides)
        # Changing a frame's box must preserve its fixed reference, not normalize
        # that frame's height to 128. Exercise both the original and added source.
        for facing, angle, index in atlas_walks[:1] + overrides:
            varied = deepcopy(self.metadata)
            frame = varied["frames"][facing][index]
            visual = self.make_visual(varied)
            count = len(varied["frames"][facing]) - 1
            visual.update(angle, (index - 0.5) * STRIDE_DISTANCE / count, 0.0)
            original_height = self.draw_arguments(visual, frame, (500.0, 300.0))[7]
            source_height = frame["clip_topleft"][3]
            frame["clip_topleft"][3] = max(1, source_height // 2)
            changed_height = self.draw_arguments(visual, frame, (500.0, 300.0))[7]
            self.assertAlmostEqual(changed_height / frame["clip_topleft"][3],
                                   original_height / source_height, places=9)

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
