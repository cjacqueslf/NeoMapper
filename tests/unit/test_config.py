import configparser
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from neomapper.infrastructure.config import save_config


class ConfigPersistenceTests(unittest.TestCase):
    def test_failed_replace_preserves_previous_config(self):
        config = configparser.ConfigParser()
        config["last"] = {"object": "99942"}

        with tempfile.TemporaryDirectory() as temporary_dir:
            target = Path(temporary_dir) / "NEOMapper_config.ini"
            target.write_text("original", encoding="utf-8")
            with patch.dict(os.environ, {"NEOMAPPER_DATA_DIR": temporary_dir}), patch(
                "neomapper.infrastructure.config.os.replace",
                side_effect=OSError("simulated interruption"),
            ):
                with self.assertRaises(OSError):
                    save_config(config)

            self.assertEqual(target.read_text(encoding="utf-8"), "original")
            self.assertEqual(list(Path(temporary_dir).glob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
