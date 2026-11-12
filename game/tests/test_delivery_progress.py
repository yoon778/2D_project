import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from game.delivery_progress import load_two_stop_unlock, save_two_stop_unlock


class DeliveryProgressTests(unittest.TestCase):
    def test_unlock_persists_and_can_be_saved_again(self):
        with TemporaryDirectory() as directory, patch.dict(os.environ, {"LOCALAPPDATA": directory}):
            self.assertFalse(load_two_stop_unlock())
            save_two_stop_unlock()
            save_two_stop_unlock()
            self.assertTrue(load_two_stop_unlock())

    def test_unavailable_save_directory_does_not_interrupt_delivery(self):
        with TemporaryDirectory() as directory, patch.dict(os.environ, {"LOCALAPPDATA": directory}):
            (Path(directory) / "DeadRoute").touch()
            save_two_stop_unlock()
            self.assertFalse(load_two_stop_unlock())
