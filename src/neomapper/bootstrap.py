"""Application composition root."""

import sys
import tempfile
from pathlib import Path


WINDOWS_APP_USER_MODEL_ID = "NEOMapper.Desktop"


def _set_windows_app_identity() -> None:
    """Give Windows a stable taskbar identity instead of Python's identity."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            WINDOWS_APP_USER_MODEL_ID
        )
    except (AttributeError, OSError):
        pass


def _animation_runtime_self_test() -> int:
    """Exercise the frozen GIF and MP4 encoders without network access."""
    try:
        import imageio.v2 as imageio
        import numpy as np

        frames = [
            np.zeros((16, 16, 3), dtype=np.uint8),
            np.full((16, 16, 3), 255, dtype=np.uint8),
        ]
        with tempfile.TemporaryDirectory(prefix="neomapper-runtime-") as temp_dir:
            root = Path(temp_dir)
            imageio.mimsave(root / "smoke.gif", frames, fps=2, loop=0)
            with imageio.get_writer(
                root / "smoke.mp4",
                fps=2,
                codec="libx264",
                macro_block_size=16,
            ) as writer:
                for frame in frames:
                    writer.append_data(frame)
            if not (root / "smoke.gif").is_file() or not (root / "smoke.mp4").is_file():
                return 1
    except Exception:
        return 1
    return 0


def _map_runtime_self_test() -> int:
    """Exercise repeated frozen Cartopy/PROJ rendering without network access."""
    try:
        import matplotlib
        matplotlib.use("Agg", force=True)
        import matplotlib.pyplot as plt
        import numpy as np
        from neomapper.presentation.mapplot import MAP_PROJECTION

        lon = np.linspace(-180.0, 180.0, 24)
        lat = np.linspace(-90.0, 90.0, 12)
        lon2d, lat2d = np.meshgrid(lon, lat)
        values = np.cos(np.deg2rad(lat2d))
        for _ in range(12):
            figure = plt.figure(figsize=(3.2, 1.8), dpi=50)
            try:
                axes = figure.add_subplot(1, 1, 1, projection=MAP_PROJECTION)
                axes.contourf(
                    lon2d,
                    lat2d,
                    values,
                    transform=MAP_PROJECTION,
                )
                figure.canvas.draw()
            finally:
                plt.close(figure)
    except Exception:
        return 1
    return 0


def main() -> int:
    if "--self-test-animation-runtime" in sys.argv:
        return _animation_runtime_self_test()
    if "--self-test-map-runtime" in sys.argv:
        return _map_runtime_self_test()

    _set_windows_app_identity()

    from neomapper.presentation.gui import run_app

    run_app()
    return 0
