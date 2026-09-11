import configparser
import os
import tempfile

from neomapper.infrastructure.paths import config_file

DEFAULTS = {
    "limits": {"animation_frames": "500", "ephemeris_rows": "500"},
    "watermark": {"text": "ASTRONEOS", "size": "medium"},
    "reference": {"enabled": "yes", "name": "Belo Horizonte, MG, Brazil", "lat": "-19.9", "lon": "-43.9", "alt": "850"},
    "time": {"mode": "UTC"},
    "map": {
        "type": "Visibility Map",
        "star_magnitude_limit": "5.0",
        "show_daynight": "yes",
        "show_civil": "yes",
        "show_nautical": "yes",
        "show_astro": "yes",
        "show_altitude": "yes",
        "show_terminator": "yes", "show_reference_point": "yes",
        "render_size": "HD",
        "dpi": "130",
    },
    "animation": {"end_offset_hours": "24", "step_minutes": "5", "fps": "5", "export_gif": "yes", "export_mp4": "yes"},
    "observing": {"min_altitude": "0", "sun_altitude_limit": "-12", "show_box": "no", "box_position": "Upper right"},
    "ui": {"language": "EN", "distance_unit": "km"},
    "preset:Belo Horizonte": {"name": "Belo Horizonte, MG, Brazil", "lat": "-19.9", "lon": "-43.9", "alt": "850"},
    "last": {"object": "99942"},
}

def load_config():
    cfg = configparser.ConfigParser()
    path = config_file()
    if path.exists():
        cfg.read(path, encoding="utf-8")
    for section, values in DEFAULTS.items():
        if section not in cfg:
            cfg[section] = values
        else:
            for k, v in values.items():
                if k not in cfg[section]:
                    cfg[section][k] = v
    return cfg

def save_config(cfg):
    path = config_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.",
            suffix=".tmp", delete=False,
        ) as temporary:
            temporary_name = temporary.name
            cfg.write(temporary)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_name, path)
    finally:
        if temporary_name:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
