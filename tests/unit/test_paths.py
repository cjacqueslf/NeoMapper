import os
import unittest
from pathlib import Path
from unittest.mock import patch

from neomapper.infrastructure.paths import config_file, logs_dir, output_dir
from neomapper.infrastructure.paths import object_output_dir
from datetime import date
import tempfile


class RuntimePathTests(unittest.TestCase):
    def test_object_folder_is_safe_and_uses_generation_date(self) -> None:
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"NEOMAPPER_DATA_DIR": folder}):
            path = object_output_dir("C/2026 A1", date(2026, 9, 9))
            self.assertEqual(path.name, "C-2026_A1-20260909")
            self.assertEqual(path.parent, output_dir())
            for designation in ("..", "../../escape", "CON", "a\\b", ""):
                self.assertEqual(object_output_dir(designation).parent, output_dir())

    def test_override_controls_all_runtime_paths(self):
        root = Path(__file__).resolve().parents[2] / "var" / "test-runtime-paths"
        root.mkdir(parents=True, exist_ok=True)
        with patch.dict(os.environ, {"NEOMAPPER_DATA_DIR": str(root)}):
            self.assertEqual(config_file(), root / "NEOMapper_config.ini")
            self.assertEqual(output_dir(), root / "output")
            self.assertEqual(logs_dir(), root / "logs")
            self.assertTrue((root / "output").is_dir())
            self.assertTrue((root / "logs").is_dir())
