from neomapper.presentation.distances import figure_distance
from pathlib import Path
from datetime import timedelta
import warnings
import numpy as np
import matplotlib
matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt
from astropy.utils.exceptions import AstropyWarning
try:
    from erfa import ErfaWarning
except Exception:
    ErfaWarning = Warning
warnings.filterwarnings("ignore", category=AstropyWarning)
warnings.filterwarnings("ignore", category=ErfaWarning)
warnings.filterwarnings("ignore", message=".*polar motions.*")
warnings.filterwarnings("ignore", message=".*dubious year.*")
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from astropy import units as u

from neomapper.application.ephemerides import parse_utc, query_horizons, query_horizons_range
from neomapper.domain.observing import (
    AU_KM,
    altitude_topocentric_grid,
    best_altitude_during_night,
    make_grid,
    max_altitude_point,
    observational_window_and_best,
    observing_night_window_utc,
    sun_altitude_grid,
)
from neomapper.application.solar_system import planet_orbit
from neomapper.presentation.i18n import Translator, format_number
from neomapper.shared.utils import format_time_for_map, parse_input_time_for_mode, suggest_output_filename
from neomapper.shared.version import APP_TITLE

# Creating and destroying a PROJ context for every animation frame can crash
# the Windows pyproj runtime. PlateCarree is immutable, so one process-wide
# instance is both safe and sufficient for every visibility-map frame.
MAP_PROJECTION = ccrs.PlateCarree()


def build_location_figure(name: str, latitude: float, longitude: float, output_png: str | None = None, language: str = "EN"):
    """Build a lightweight world-map preview for the selected reference site."""
    fig = plt.figure(figsize=(8.2, 4.6), dpi=120, facecolor="#071017")
    ax = fig.add_subplot(1, 1, 1, projection=MAP_PROJECTION)
    ax.set_global()
    ax.set_facecolor("#0b2638")
    ax.add_feature(cfeature.LAND, facecolor="#173b4d", edgecolor="#426276", linewidth=.4)
    ax.add_feature(cfeature.OCEAN, facecolor="#0b2638")
    ax.coastlines(color="#6e8c9b", linewidth=.45)
    ax.gridlines(color="#6e8c9b", alpha=.22, linewidth=.35, linestyle="--")
    ax.scatter([float(longitude)], [float(latitude)], transform=MAP_PROJECTION,
               s=90, color="#ffcc33", edgecolors="#201b00", linewidths=.9, zorder=4)
    ax.text(float(longitude) + 5, float(latitude) + 4,
            f"{name}\n{float(latitude):.4f}°, {float(longitude):.4f}°",
            transform=MAP_PROJECTION, color="white", fontsize=10,
            bbox=dict(boxstyle="round,pad=.35", facecolor="#0b1521", edgecolor="#ffcc33", alpha=.94),
            zorder=5)
    ax.set_title(Translator(language).tr("Reference location"), color="white", fontsize=14, weight="bold")
    fig.tight_layout()
    if output_png:
        path = Path(output_png); path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, dpi=120, facecolor=fig.get_facecolor())
    return fig


def build_solar_system_sketch(object_name: str, object_distance_au: float, output_png: str | None = None, obstime=None, semi_major_au: float | None = None, eccentricity: float = 0.0, object_xy: tuple[float, float] | None = None, orbit_angle_deg: float = 0.0, distance_unit: str = "km", language: str = "EN", object_path_au: np.ndarray | None = None):
    """Draw a schematic heliocentric layout with adaptive outer scale."""
    import matplotlib.pyplot as plt
    from astropy.time import Time
    tr = Translator(language).tr
    labels = ["Mercury", "Venus", "Earth", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune"]
    radii = list(zip(labels, [.387, .723, 1.0, 1.524, 5.203, 9.537, 19.19, 30.07], ["#b8afa4", "#e7c58b", "#5ba9e6", "#ef765a", "#e5c49d", "#e6d18b", "#9bdce2", "#739cf2"]))
    distance = max(.01, float(object_distance_au))
    orbit_a = float(semi_major_au) if semi_major_au is not None else distance
    eccentricity = float(eccentricity)
    if orbit_a <= 0 or not 0 <= eccentricity < 1:
        raise ValueError("A bound elliptic orbit is required")
    orbit_aphelion = orbit_a * (1.0 + eccentricity)
    limit = next((radius for _name, radius, _color in radii if radius >= orbit_aphelion), orbit_aphelion * 1.15)
    limit = max(limit * 1.12, 1.8)
    fig, ax = plt.subplots(figsize=(7.5, 6.2), dpi=120, facecolor="#071017")
    ax.set_facecolor("#071017"); ax.set_aspect("equal"); ax.set_xlim(-limit, limit); ax.set_ylim(-limit, limit)
    t = Time(obstime) if obstime is not None else Time.now()
    for name, radius, color in radii:
        body_key = dict(zip(labels, ["mercury", "venus", "earth", "mars", "jupiter", "saturn", "uranus", "neptune"]))[name]
        if radius > limit: break
        position, path = planet_orbit(body_key, t)
        ax.plot(path[:, 0], path[:, 1], color="#4a6678", alpha=.55, lw=.7)
        px, py = position[:2]
        ax.scatter([px], [py], s=38, color=color, edgecolors="white", linewidths=.35, zorder=3)
        ax.text(px, py + .04 * limit, tr(name), color=color, fontsize=8, ha="center", gid="solar-label:" + name)
    theta = .55
    anomaly = np.linspace(0, 2*np.pi, 500)
    orbit_x = orbit_a * (np.cos(anomaly) - eccentricity)
    orbit_y = orbit_a * np.sqrt(1.0 - eccentricity**2) * np.sin(anomaly)
    angle = np.radians(float(orbit_angle_deg))
    rotated_x = orbit_x*np.cos(angle) - orbit_y*np.sin(angle)
    rotated_y = orbit_x*np.sin(angle) + orbit_y*np.cos(angle)
    if object_path_au is not None:
        # Orthographic projection of the same 3D state used for the marker.
        rotated_x, rotated_y = object_path_au[:, 0], object_path_au[:, 1]
    ax.plot(rotated_x, rotated_y, color="#ffcc33", alpha=.85, lw=1.2, ls="--")
    object_x, object_y = object_xy if object_xy is not None else (distance*np.cos(theta), distance*np.sin(theta))
    ax.scatter([object_x], [object_y], s=85, color="#ffcc33", edgecolors="#241d00", zorder=5)
    ax.text(object_x, object_y+.07*limit, object_name, color="#ffcc33", fontsize=9, ha="center", weight="bold")
    ax.scatter([0], [0], s=180, color="#ffd34e", edgecolors="#5b4300", zorder=6)
    ax.text(0, -.09*limit, tr("Sun"), color="#ffd34e", ha="center", fontsize=9, gid="solar-label:Sun")
    fig._solar_title_data = (object_name, t.utc.datetime.strftime("%Y-%m-%d"), orbit_a * AU_KM, eccentricity)
    update_solar_system_labels(fig, language, distance_unit)
    ax.axis("off"); fig.tight_layout()
    if output_png:
        path = Path(output_png); path.parent.mkdir(parents=True, exist_ok=True); fig.savefig(path, dpi=120, facecolor=fig.get_facecolor())
    return fig


def update_solar_system_labels(figure: plt.Figure, language: str, distance_unit: str) -> None:
    """Relabel the existing figure without querying or changing orbital geometry."""
    tr = Translator(language).tr
    ax = figure.axes[0]
    for artist in ax.texts:
        key = artist.get_gid() or ""
        if key.startswith("solar-label:"):
            artist.set_text(tr(key.removeprefix("solar-label:")))
    name, date, distance_km, eccentricity = figure._solar_title_data
    figure._distance_labels = []
    distance = figure_distance(figure, distance_km, distance_unit, language)
    ax.set_title(f'{tr("Solar System")} — {name}\n{date} | a={distance}, e={format_number(eccentricity, 3, language, False)}',
                 color="white", weight="bold")

def add_watermark(fig, text="ASTRONEOS", size="medium"):
    fontsize = {"small": 18, "medium": 28, "large": 38}.get(size, 28)
    fig.text(0.975, 0.045, text, ha="right", va="bottom", fontsize=fontsize, weight="bold", color="white", alpha=0.22)

def add_twilight_legend(fig, language="EN", show_daynight=True, show_civil=True, show_nautical=True, show_astro=True, show_terminator=True):
    # Dynamic legend: only show the layers actually enabled in the map.
    if not show_daynight and not show_terminator:
        return
    if (language or "EN").upper() == "PT":
        title = "Legenda"
        items = []
        if show_daynight:
            items.append(("Dia", "#d8d8d8"))
        if show_daynight and show_civil:
            items.append(("Crepúsculo Civil", "#a6b0c5"))
        if show_daynight and show_nautical:
            items.append(("Crepúsculo Náutico", "#41577c"))
        if show_daynight and show_astro:
            items.append(("Crepúsculo Astronômico", "#1b2440"))
        if show_daynight:
            items.append(("Noite", "#020611"))
        if show_terminator:
            items.append(("Terminador", "#bfc7d8"))
    elif (language or "EN").upper() == "ES":
        title = "Leyenda"
        items = []
        if show_daynight:
            items.append(("Día", "#d8d8d8"))
        if show_daynight and show_civil:
            items.append(("Crepúsculo civil", "#a6b0c5"))
        if show_daynight and show_nautical:
            items.append(("Crepúsculo náutico", "#41577c"))
        if show_daynight and show_astro:
            items.append(("Crepúsculo astronómico", "#1b2440"))
        if show_daynight:
            items.append(("Noche", "#020611"))
        if show_terminator:
            items.append(("Terminador", "#bfc7d8"))
    else:
        title = "Legend"
        items = []
        if show_daynight:
            items.append(("Day", "#d8d8d8"))
        if show_daynight and show_civil:
            items.append(("Civil twilight", "#a6b0c5"))
        if show_daynight and show_nautical:
            items.append(("Nautical twilight", "#41577c"))
        if show_daynight and show_astro:
            items.append(("Astronomical twilight", "#1b2440"))
        if show_daynight:
            items.append(("Night", "#020611"))
        if show_terminator:
            items.append(("Terminator", "#bfc7d8"))

    x0, y0, dy = 0.035, 0.275, 0.027
    fig.text(x0, y0 + 0.035, title, ha="left", va="center", fontsize=8.5, color="white", alpha=0.95, weight="bold", zorder=21)
    for i, (label, color) in enumerate(items):
        y = y0 - i * dy
        fig.patches.append(
            plt.Rectangle((x0, y - 0.006), 0.017, 0.014, transform=fig.transFigure,
                          facecolor=color, edgecolor="white", linewidth=0.35, alpha=0.85, zorder=20)
        )
        fig.text(x0 + 0.023, y, label, ha="left", va="center", fontsize=8, color="white", alpha=0.92, zorder=21)

def draw_reference_point(ax, proj, name, lat, lon):
    ax.scatter([lon], [lat], transform=proj, s=70, color="#74ff3b", edgecolor="black", linewidth=0.7, zorder=8)
    ax.text(lon + 3, lat - 4, f"{name}", transform=proj, color="#74ff3b", fontsize=9, weight="bold", zorder=8,
            bbox=dict(facecolor="black", edgecolor="none", alpha=0.35, pad=2.0))


def figure_size_from_render_size(render_size: str, dpi: int):
    """
    Retorna figsize fixa para garantir que todos os frames tenham exatamente
    a mesma dimensão em pixels. Isto é essencial para GIF/MP4.
    """
    render_size = (render_size or "HD").upper()
    if render_size in ("4K", "UHD"):
        width_px, height_px = 3840, 2160
    elif render_size in ("2K", "QHD", "1440P"):
        width_px, height_px = 2560, 1440
    elif render_size in ("FHD", "1080P", "FULLHD"):
        width_px, height_px = 1920, 1080
    else:
        width_px, height_px = 1280, 720
    return (width_px / dpi, height_px / dpi), (width_px, height_px)



def map_label(key: str, language="EN"):
    labels_pt = {"distance": "Distância", "max_altitude": "Ponto de Máxima Visibilidade"}
    labels_es = {"distance": "Distancia", "max_altitude": "Punto de máxima visibilidad"}
    labels_en = {"distance": "Distance", "max_altitude": "Maximum Visibility Point"}
    lang=(language or "EN").upper()
    labels = labels_pt if lang == "PT" else (labels_es if lang == "ES" else labels_en)
    return labels.get(key, key)


def build_visibility_figure(
    object_query: str,
    utc_text: str,
    output_png: str | None = None,
    step_deg: float = 1.0,
    dpi: int = 130,
    watermark_text: str = "ASTRONEOS",
    watermark_size: str = "medium",
    reference_enabled: bool = True,
    reference_name: str = "Observatório Y05",
    reference_lat: float = -19.9,
    reference_lon: float = -43.9,
    show_daynight: bool = True,
    show_civil: bool = True,
    show_nautical: bool = True,
    show_astro: bool = True,
    show_altitude: bool = True,
    show_terminator: bool = True,
    time_mode: str = "UTC",
    render_size: str = "HD",
    language: str = "EN",
    obs_min_altitude: float = 0.0,
    obs_sun_altitude_limit: float = -12.0,
    show_obs_box: bool = False,
    obs_box_position: str = "upper right",
    trail_positions=None,
    distance_unit: str = "km",
    display_time_mode: str | None = None,
    reference_alt: float = 0.0,
):
    t = parse_input_time_for_mode(utc_text, time_mode, reference_lat, reference_lon)
    time_mode = display_time_mode or time_mode
    h = query_horizons(object_query, t)

    lon2d, lat2d = make_grid(step_deg)
    alt, _ = altitude_topocentric_grid(h, t, lon2d, lat2d)
    sun_alt = sun_altitude_grid(t, lon2d, lat2d)
    zen_lat, zen_lon, zen_alt = max_altitude_point(alt, lon2d, lat2d)

    proj = MAP_PROJECTION
    figsize, pixel_size = figure_size_from_render_size(render_size, dpi)
    fig = plt.figure(figsize=figsize, dpi=dpi, facecolor="#101417")
    ax = plt.axes(projection=proj)
    ax.set_global()
    ax.set_facecolor("#0b3045")

    ax.add_feature(cfeature.OCEAN, facecolor="#0b3045")
    ax.add_feature(cfeature.LAND, facecolor="#657f4b")
    ax.add_feature(cfeature.COASTLINE, linewidth=0.35, edgecolor="#d7d7d7", alpha=0.65)
    ax.add_feature(cfeature.BORDERS, linewidth=0.20, edgecolor="#d7d7d7", alpha=0.42)
    ax.gridlines(draw_labels=False, linewidth=0.18, alpha=0.18, color="white")

    if show_daynight:
        ax.contourf(lon2d, lat2d, sun_alt, levels=[-90, -18], colors=["#020611"], alpha=0.67, transform=proj)
        if show_astro:
            ax.contourf(lon2d, lat2d, sun_alt, levels=[-18, -12], colors=["#1b2440"], alpha=0.45, transform=proj)
        if show_nautical:
            ax.contourf(lon2d, lat2d, sun_alt, levels=[-12, -6], colors=["#41577c"], alpha=0.34, transform=proj)
        if show_civil:
            ax.contourf(lon2d, lat2d, sun_alt, levels=[-6, 0], colors=["#a6b0c5"], alpha=0.28, transform=proj)

        twilight_levels = []
        if show_astro: twilight_levels.append(-18)
        if show_nautical: twilight_levels.append(-12)
        if show_civil: twilight_levels.append(-6)
        if twilight_levels:
            ax.contour(lon2d, lat2d, sun_alt, levels=twilight_levels, colors="#bfc7d8", linewidths=0.65, alpha=0.65, transform=proj)
        if show_terminator:
            ax.contour(lon2d, lat2d, sun_alt, levels=[0], colors="#ffffff", linewidths=0.95, alpha=0.85, transform=proj)
    elif show_terminator:
        ax.contour(lon2d, lat2d, sun_alt, levels=[0], colors="#ffffff", linewidths=0.95, alpha=0.85, transform=proj)

    if show_altitude:
        ax.contourf(lon2d, lat2d, alt, levels=[0, 90], colors=["#f4c542"], alpha=0.08, transform=proj)
        cs = ax.contour(lon2d, lat2d, alt, levels=[0, 15, 30, 45, 60, 75], colors="#ffd400",
                        linewidths=0.72, alpha=0.95, transform=proj)
        lang=(language or "EN").upper()
        horizon_label = "horizonte" if lang in ("PT","ES") else "horizon"
        labels = ax.clabel(cs, inline=True, fmt=lambda v: horizon_label if abs(v) < 0.01 else f"{int(v)}°",
                           fontsize=9, colors="#ffd400")
        for lbl in labels:
            lbl.set_fontweight("bold")
            lbl.set_bbox(dict(facecolor="black", edgecolor="none", alpha=0.25, pad=1.2))

    if trail_positions:
        trail = [(float(lon), float(lat)) for lon, lat in trail_positions]
        trail.append((zen_lon, zen_lat))
        trail_lons, trail_lats = zip(*trail)
        ax.plot(trail_lons, trail_lats, transform=proj, color="#ff8c00",
                linewidth=2.0, alpha=0.9, zorder=6)
        ax.scatter(trail_lons[:-1], trail_lats[:-1], transform=proj, s=16,
                   color="#ffb347", edgecolor="black", linewidth=0.25,
                   alpha=0.75, zorder=6)

    ax.scatter([zen_lon], [zen_lat], s=44, marker="o", transform=proj, zorder=7, color="#ffd400", edgecolor="black", linewidth=0.5)
    ax.text(zen_lon + 3, zen_lat + 3, map_label("max_altitude", language), fontsize=9, weight="bold", transform=proj, color="#ffd400",
            bbox=dict(facecolor="black", edgecolor="none", alpha=0.28, pad=1.5))

    if reference_enabled:
        draw_reference_point(ax, proj, reference_name, float(reference_lat), float(reference_lon))

    geo_km = getattr(h, 'distance_km', h.delta_au * AU_KM)
    vmag_txt = "—" if h.vmag is None else format_number(h.vmag,2,language,False)
    display_time, display_label = format_time_for_map(t, time_mode, reference_lat, reference_lon)

    # Observational Window at the reference site: configurable solar-altitude limit + object altitude >= minimum.
    best_altitude = None
    best_altitude_time = None
    best_altitude_display_time = None
    best_altitude_display_label = None
    best_altitude_az = None
    best_altitude_sun_alt = None
    best_altitude_reason = "not_calculated"
    observing_start = None
    observing_stop = None
    observing_night_label = None
    dark_start = None
    dark_stop = None
    try:
        observing_start, observing_stop, night_date = observing_night_window_utc(t, float(reference_lon))
        observing_night_label = f"{night_date:%Y-%m-%d}/{(night_date + timedelta(days=1)):%Y-%m-%d}"
        eph_range = query_horizons_range(object_query, observing_start, observing_stop, step="5m")
        obs = observational_window_and_best(eph_range, float(reference_lat), float(reference_lon), min_altitude_deg=float(obs_min_altitude), sun_limit_deg=float(obs_sun_altitude_limit), height_m=float(reference_alt))
        dark_start = obs.get("dark_start")
        dark_stop = obs.get("dark_stop")
        observing_start = obs.get("window_start") or observing_start
        observing_stop = obs.get("window_stop") or observing_stop
        best = obs.get("best")
        best_altitude_reason = getattr(best, "reason", "not_calculated")
        if best and best.altitude_deg is not None:
            best_altitude = float(best.altitude_deg)
            best_altitude_time = best.time.utc.iso if best.time is not None else None
            best_altitude_az = best.az_deg
            best_altitude_sun_alt = best.sun_alt_deg
            if best.time is not None:
                best_altitude_display_time, best_altitude_display_label = format_time_for_map(best.time, time_mode, reference_lat, reference_lon)
    except Exception as exc:
        best_altitude_reason = f"error: {exc}"

    def fmt_time_obj(tt):
        if tt is None:
            return "—"
        txt, lab = format_time_for_map(tt, time_mode, reference_lat, reference_lon)
        return f"{txt[11:16]} {lab}"

    if show_obs_box:
        lang=(language or "EN").upper(); pt=lang=="PT"; es=lang=="ES"
        box_title = "Janela Observacional" if pt else ("Ventana observacional" if es else "Observational Window")
        dark_label = f"Sol ≤ {float(obs_sun_altitude_limit):.0f}°" if (pt or es) else f"Sun ≤ {float(obs_sun_altitude_limit):.0f}°"
        obj_label = f"Objeto ≥ {float(obs_min_altitude):.0f}°" if (pt or es) else f"Object ≥ {float(obs_min_altitude):.0f}°"
        best_label_txt = "Melhor" if pt else ("Mejor" if es else "Best")
        if best_altitude is None:
            best_txt = "—"
        else:
            best_txt = f"{fmt_time_obj(best.time)} / {format_number(best_altitude,1,language,False)}°"
        box_text = (f"{box_title}\n"
                    f"{dark_label}: {fmt_time_obj(dark_start)}–{fmt_time_obj(dark_stop)}\n"
                    f"{obj_label}: {fmt_time_obj(observing_start)}–{fmt_time_obj(observing_stop)}\n"
                    f"{best_label_txt}: {best_txt}")
        pos = (obs_box_position or "upper right").lower()
        x = 0.035 if "left" in pos else 0.965
        y = 0.86 if "upper" in pos else 0.14
        ha = "left" if "left" in pos else "right"
        va = "top" if "upper" in pos else "bottom"
        fig.text(x, y, box_text, ha=ha, va=va, fontsize=8.8, color="white", alpha=0.95,
                 bbox=dict(facecolor="black", edgecolor="#9aa8b5", linewidth=0.6, alpha=0.55, boxstyle="round,pad=0.45"), zorder=30)

    # Adaptive title: one line when it fits, two lines for narrower/HD exports.
    title_left = f"{h.targetname} — {display_time} {display_label}"
    title_right = f"{map_label('distance', language)}: {figure_distance(fig, geo_km, distance_unit, language)} | V: {vmag_txt}"
    full_title = f"{title_left}   | {title_right}"
    # Use a conservative character threshold by render width. This avoids text being clipped in HD.
    max_chars = 92 if pixel_size[0] <= 1280 else 120 if pixel_size[0] <= 1920 else 150
    title_text = full_title if len(full_title) <= max_chars else f"{title_left}\n{title_right}"
    ax.set_title(title_text, fontsize=12, color="white", weight="bold", pad=10, linespacing=1.25)

    fig.text(0.018, 0.045, APP_TITLE, ha="left", va="bottom", fontsize=9, color="white", alpha=0.72, weight="bold")
    add_twilight_legend(fig, language, show_daynight, show_civil, show_nautical, show_astro, show_terminator)
    add_watermark(fig, watermark_text, watermark_size)
    fig.subplots_adjust(left=0.015, right=0.985, top=0.92, bottom=0.045)

    result = {
        "targetname": h.targetname, "utc": h.utc_iso, "display_time": display_time, "display_label": display_label, "zen_lat": zen_lat, "zen_lon": zen_lon,
        "zen_alt": zen_alt, "geo_km": geo_km, "vmag": h.vmag,
        "ephemeris_source": h.source,
        "best_altitude": best_altitude,
        "best_altitude_time": best_altitude_time,
        "best_altitude_display_time": best_altitude_display_time,
        "best_altitude_display_label": best_altitude_display_label,
        "best_altitude_az": best_altitude_az,
        "best_altitude_sun_alt": best_altitude_sun_alt,
        "best_altitude_reason": best_altitude_reason,
        "observing_night_label": observing_night_label,
        "observing_window_start_utc": observing_start.utc.datetime.strftime("%Y-%m-%d %H:%M:%S") if observing_start is not None else None,
        "observing_window_stop_utc": observing_stop.utc.datetime.strftime("%Y-%m-%d %H:%M:%S") if observing_stop is not None else None,
        "dark_start_utc": dark_start.utc.datetime.strftime("%Y-%m-%d %H:%M:%S") if dark_start is not None else None,
        "dark_stop_utc": dark_stop.utc.datetime.strftime("%Y-%m-%d %H:%M:%S") if dark_stop is not None else None,
        "obs_min_altitude": float(obs_min_altitude),
        "obs_sun_altitude_limit": float(obs_sun_altitude_limit),
        "observing_window_start_display": format_time_for_map(observing_start, time_mode, reference_lat, reference_lon)[0] if observing_start is not None else None,
        "observing_window_stop_display": format_time_for_map(observing_stop, time_mode, reference_lat, reference_lon)[0] if observing_stop is not None else None,
        "suggested_filename": suggest_output_filename(object_query, utc_text, h.targetname),
        "output": output_png,
        "pixel_size": pixel_size,
    }

    if output_png:
        output_path = Path(output_png)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=dpi, facecolor=fig.get_facecolor())
        result["output"] = str(output_path)

    return fig, result
