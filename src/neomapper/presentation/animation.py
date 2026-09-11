from pathlib import Path
import warnings
import shutil
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import numpy as np
try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except Exception:
    Image = ImageDraw = ImageFont = None
    HAS_PIL = False
warnings.filterwarnings("ignore", message=".*dubious year.*")
warnings.filterwarnings("ignore", message=".*polar motions.*")

try:
    import imageio.v2 as imageio
    HAS_IMAGEIO = True
    IMAGEIO_IMPORT_ERROR = None
except Exception as exc:
    imageio = None
    HAS_IMAGEIO = False
    IMAGEIO_IMPORT_ERROR = exc

from neomapper.presentation.mapplot import build_visibility_figure
from neomapper.presentation.skymap import build_sky_figure
from neomapper.shared.utils import parse_input_time_for_mode

def _normalize_rgba(img):
    arr = np.asarray(img)
    if arr.ndim == 2:
        arr = np.stack([arr, arr, arr], axis=-1)
    if arr.shape[-1] == 4:
        return arr
    if arr.shape[-1] == 3:
        alpha = np.full(arr.shape[:2] + (1,), 255, dtype=arr.dtype)
        return np.concatenate([arr, alpha], axis=-1)
    return arr

def _pad_or_crop_to_shape(arr, target_shape):
    """
    Garante que todos os frames tenham o mesmo shape.
    Se por algum motivo algum PNG sair 1 ou 2 pixels diferente, centraliza
    em uma tela preta do tamanho padrão.
    """
    arr = _normalize_rgba(arr)
    th, tw, tc = target_shape
    h, w, c = arr.shape
    out = np.zeros((th, tw, tc), dtype=arr.dtype)
    out[..., 3] = 255
    copy_h = min(h, th)
    copy_w = min(w, tw)
    y0 = max((th - copy_h) // 2, 0)
    x0 = max((tw - copy_w) // 2, 0)
    sy0 = max((h - copy_h) // 2, 0)
    sx0 = max((w - copy_w) // 2, 0)
    out[y0:y0+copy_h, x0:x0+copy_w, :min(c, tc)] = arr[sy0:sy0+copy_h, sx0:sx0+copy_w, :min(c, tc)]
    return out

def read_frames_same_shape(frame_files):
    imgs = [_normalize_rgba(imageio.imread(f)) for f in frame_files]
    # Usa o shape mais frequente/maior como alvo; na v2.3 todos já deveriam ser iguais.
    max_h = max(img.shape[0] for img in imgs)
    max_w = max(img.shape[1] for img in imgs)
    target = (max_h, max_w, 4)
    return [_pad_or_crop_to_shape(img, target) for img in imgs]


def generate_animation(
    *,
    object_query: str,
    start_time: str,
    end_time: str | None = None,
    base_output: str = "animation.png",
    step_minutes: int = 5,
    max_frames: int = 500,
    calendar_step: str | None = None,
    fps: int,
    export_gif: bool,
    export_mp4: bool,
    keep_frames: bool = True,
    trail_enabled: bool = False,
    time_label_enabled: bool = False,
    map_type: str = "visibility",
    progress_callback=None,
    preview_callback=None,
    cancel_callback=None,
    **map_kwargs,
):
    if not HAS_IMAGEIO:
        raise RuntimeError(
            Translator(map_kwargs.get("language", "EN")).tr("Could not load imageio: {error}", error=IMAGEIO_IMPORT_ERROR)
        ) from IMAGEIO_IMPORT_ERROR

    time_mode = map_kwargs.get("time_mode", "UTC")
    ref_lat = float(map_kwargs.get("reference_lat", -19.9))
    ref_lon = float(map_kwargs.get("reference_lon", -43.9))
    start = parse_input_time_for_mode(start_time, time_mode, ref_lat, ref_lon).utc.datetime.replace(tzinfo=None)

    if end_time is None:
        end = start + timedelta(hours=4)
    else:
        end = parse_input_time_for_mode(end_time, time_mode, ref_lat, ref_lon).utc.datetime.replace(tzinfo=None)

    if end <= start:
        end = start + timedelta(minutes=max(1, int(step_minutes)))

    step_minutes = max(1, int(step_minutes))
    from neomapper.application.generation_limits import sample_count, enforce_limit, GenerationLimitError
    from neomapper.presentation.i18n import Translator
    frame_count = sample_count((end - start).total_seconds(), step_minutes * 60, include_end=True)
    try:
        if calendar_step:
            from neomapper.application.animation_schedule import calendar_frames
            civil_start = datetime.fromisoformat(start_time)
            civil_end = datetime.fromisoformat(end_time) if end_time else civil_start + timedelta(hours=4)
            requested_times = calendar_frames(civil_start, civil_end, calendar_step, max_frames)
            times = [parse_input_time_for_mode(dt.isoformat(sep=" "), time_mode, ref_lat, ref_lon).utc.datetime.replace(tzinfo=None) for dt in requested_times]
        else:
            enforce_limit(frame_count, max_frames)
            times = [start + timedelta(minutes=i * step_minutes) for i in range(frame_count - 1)] + [end]
    except GenerationLimitError as exc:
        raise ValueError(Translator(map_kwargs.get("language", "EN")).tr(
            "Frame limit exceeded", count=exc.count, limit=exc.limit)) from exc

    base_path = Path(base_output).with_suffix("")
    frames_dir = base_path.with_name(base_path.name + "_frames")
    # Frames are always needed while encoding, but only persistent PNG output
    # should leave this directory behind.
    frames_dir.mkdir(parents=True, exist_ok=True)

    frame_files = []
    visible_times = []
    previous_positions = []
    last_result = None
    sky_visibility_started = False

    for idx, dt in enumerate(times):
        if cancel_callback and cancel_callback():
            raise RuntimeError("Animation cancelled by user")
        frame_file = frames_dir / f"frame_{idx:04d}.png"
        is_sky_map = str(map_type).strip().lower() in {"sky", "sky map", "celeste", "mapa celeste"}
        builder = build_sky_figure if is_sky_map else build_visibility_figure
        frame_kwargs = dict(map_kwargs)
        # ``dt`` is normalized to UTC above. Do not let the renderer apply the
        # LOCAL offset a second time when the animation controls use local time.
        frame_kwargs["time_mode"] = "UTC"
        frame_kwargs["display_time_mode"] = time_mode
        if not is_sky_map:
            frame_kwargs.pop("show_info_panel", None)
        fig, result = builder(
            object_query=object_query,
            utc_text=dt.strftime("%Y-%m-%d %H:%M:%S"),
            output_png=str(frame_file),
            trail_positions=previous_positions if trail_enabled else None,
            **frame_kwargs,
        )
        plt.close(fig)

        # A sky animation covers one continuous visibility interval. Ignore
        # samples before rise and stop permanently at the first sample after
        # set, so neither the target nor the surrounding sky keeps moving while
        # the target is below the geometric horizon.
        if is_sky_map and float(result["current_altitude"]) < 0.0:
            frame_file.unlink(missing_ok=True)
            if progress_callback:
                progress_callback(idx + 1, len(times), "")
            if sky_visibility_started:
                break
            continue

        if is_sky_map:
            sky_visibility_started = True
            # Sky trails are anchored to the celestial sphere. The renderer
            # projects these equatorial marks into the AltAz frame of every
            # subsequent animation instant, so they rotate with the stars.
            if trail_enabled:
                previous_positions.append((
                    result["current_azimuth"], result["current_altitude"],
                    dt.strftime("%Y-%m-%d %H:%M:%S"),
                ))
        elif trail_enabled:
            previous_positions.append((result["zen_lon"], result["zen_lat"]))

        last_result = result
        visible_times.append(dt)

        if time_label_enabled and HAS_PIL:
            try:
                img = Image.open(frame_file).convert("RGBA")
                draw = ImageDraw.Draw(img)
                from astropy.time import Time
                from neomapper.shared.utils import format_time_for_map
                shown, zone = format_time_for_map(Time(dt, scale="utc"), time_mode, ref_lat, ref_lon)
                label = f"{shown} {zone}"
                box = (14, img.height - 46, 260, img.height - 14)
                draw.rectangle(box, fill=(0, 0, 0, 150), outline=(180, 180, 180, 120))
                draw.text((24, img.height - 38), label, fill=(255, 255, 255, 245))
                img.save(frame_file)
            except Exception:
                pass
        frame_files.append(frame_file)
        if preview_callback:
            preview_callback(str(frame_file), idx + 1, len(times))
        if progress_callback:
            progress_callback(idx + 1, len(times), str(frame_file))

    if is_sky_map and not frame_files:
        language = str(map_kwargs.get("language", "EN")).upper()
        message = {
            "PT": "O objeto permanece abaixo do horizonte durante todo o intervalo selecionado",
            "ES": "El objeto permanece bajo el horizonte durante todo el intervalo seleccionado",
        }.get(language, "The object remains below the horizon throughout the selected interval")
        shutil.rmtree(frames_dir, ignore_errors=True)
        raise ValueError(message)

    if cancel_callback and cancel_callback():
        raise RuntimeError("Animation cancelled by user")

    outputs = []

    if cancel_callback and cancel_callback():
        raise RuntimeError("Animation cancelled by user")

    if export_gif:
        gif_path = base_path.with_suffix(".gif")
        imgs = read_frames_same_shape(frame_files)
        imageio.mimsave(gif_path, imgs, fps=fps, loop=0)
        outputs.append(str(gif_path))

    if export_mp4:
        mp4_path = base_path.with_suffix(".mp4")
        imgs = read_frames_same_shape(frame_files)
        writer = imageio.get_writer(mp4_path, fps=fps, codec="libx264", quality=8, macro_block_size=16)
        for img in imgs:
            if cancel_callback and cancel_callback():
                writer.close()
                raise RuntimeError("Animation cancelled by user")
            writer.append_data(img)
        writer.close()
        outputs.append(str(mp4_path))

    returned_frames_dir = str(frames_dir)
    if not keep_frames:
        # Keep the final PNG visible for preview, but remove the temporary frame folder.
        try:
            shutil.rmtree(frames_dir)
        except Exception:
            pass

    return {
        "outputs": outputs,
        "frames_dir": returned_frames_dir,
        "last_fig": None,
        "last_result": last_result,
        "frame_count": len(frame_files),
        "effective_start_time": visible_times[0].strftime("%Y-%m-%d %H:%M:%S") if visible_times else None,
        "effective_end_time": visible_times[-1].strftime("%Y-%m-%d %H:%M:%S") if visible_times else None,
    }
