from neomapper.presentation.lunar_marker import draw_moon
from neomapper.domain.sky_brightness import atmospheric_magnitude, star_visibility, milky_way_visibility
from neomapper.presentation.sky_visibility import target_status
from neomapper.presentation.distances import figure_distance
from pathlib import Path
import matplotlib
matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt
import numpy as np
from astropy import units as u
from astropy.coordinates import (AltAz, EarthLocation, GCRS, SkyCoord, get_body,
                                 get_sun, solar_system_ephemeris)
from astropy.utils import iers
from neomapper.application.ephemerides import query_horizons
from neomapper.domain.observing import AU_KM
from neomapper.presentation.i18n import Translator, format_number
from neomapper.presentation.mapplot import add_watermark, figure_size_from_render_size
from neomapper.presentation.skyplot import celestial_trail_to_horizontal, visible_target_path
from neomapper.shared.utils import format_time_for_map, parse_input_time_for_mode, suggest_output_filename
from neomapper.shared.version import APP_TITLE

iers.conf.auto_download = False
iers.conf.auto_max_age = None
_CATALOG = None

SOLAR_SYSTEM_BODIES = {
    "sun": ("Sun", "#ffd34e", 150, r"$\odot$"),
    "moon": ("Moon", "#e8edf2", 125, "o"),
    "mercury": ("Mercury", "#b8afa4", 42, "o"),
    "venus": ("Venus", "#fff0bd", 78, "o"),
    "mars": ("Mars", "#ef765a", 58, "o"),
    "jupiter": ("Jupiter", "#e5c49d", 82, "o"),
    "saturn": ("Saturn", "#e6d18b", 68, "o"),
    "uranus": ("Uranus", "#9bdce2", 46, "o"),
    "neptune": ("Neptune", "#739cf2", 44, "o"),
}

SOLAR_SYSTEM_LABELS_PT = {
    "sun": "Sol", "moon": "Lua", "mercury": "Mercúrio",
    "venus": "Vênus", "mars": "Marte", "jupiter": "Júpiter",
    "saturn": "Saturno", "uranus": "Urano", "neptune": "Netuno",
}
SOLAR_SYSTEM_LABELS_ES = {
    "sun": "Sol", "moon": "Luna", "mercury": "Mercurio",
    "venus": "Venus", "mars": "Marte", "jupiter": "Júpiter",
    "saturn": "Saturno", "uranus": "Urano", "neptune": "Neptuno",
}

def _solar_system_positions(t, loc, frame):
    """Return topocentric positions using Astropy's bundled ephemeris."""
    positions = {}
    with solar_system_ephemeris.set("builtin"):
        for key, (label, color, size, marker) in SOLAR_SYSTEM_BODIES.items():
            coord = get_sun(t) if key == "sun" else get_body(key, t, loc)
            horizontal = coord.transform_to(frame)
            positions[key] = {
                "label": label, "color": color, "size": size, "marker": marker,
                "az": float(horizontal.az.deg), "alt": float(horizontal.alt.deg),
                "distance_au": float(horizontal.distance.to_value(u.au)),
            }
    return positions

def _load_hipparcos_catalog():
    """Load the compact offline Hipparcos subset (V <= 7) once per process."""
    global _CATALOG
    if _CATALOG is None:
        path = Path(__file__).with_name("data") / "hipparcos_bright.npz"
        with np.load(path) as data:
            _CATALOG = {key: data[key].copy() for key in data.files}
    return _CATALOG

def _bv_colors(bv):
    """Approximate apparent RGB from the Hipparcos Johnson B-V index."""
    values=np.nan_to_num(np.asarray(bv,dtype=float),nan=.65)
    knots=np.array([-.40,0.00,.40,.80,1.30,2.00])
    red=np.array([.62,.78,.94,1.00,1.00,1.00])
    green=np.array([.76,.87,.96,.94,.76,.56])
    blue=np.array([1.00,1.00,1.00,.78,.50,.32])
    return np.column_stack([np.interp(values,knots,red),np.interp(values,knots,green),np.interp(values,knots,blue)])

def _hex_rgb(value):
    value=value.lstrip("#")
    return np.array([int(value[i:i+2],16)/255.0 for i in (0,2,4)])

def _sky_colors(sun_altitude):
    """Continuous blue sky palette through day and all twilight stages."""
    # Solar-altitude anchors: full day, sunset, civil, nautical,
    # astronomical twilight and deep night.
    anchors=np.array([-24.0,-18.0,-12.0,-6.0,0.0,12.0])
    zenith=["#01040b","#030916","#091a31","#17446f","#2b70a2","#3e86b6"]
    horizon=["#050b16","#09162a","#163554","#326b97","#568faf","#70aacb"]
    altitude=float(np.clip(sun_altitude,anchors[0],anchors[-1]))
    z=np.array([np.interp(altitude,anchors,[_hex_rgb(c)[i] for c in zenith]) for i in range(3)])
    h=np.array([np.interp(altitude,anchors,[_hex_rgb(c)[i] for c in horizon]) for i in range(3)])
    return z,h

# Small offline J2000 catalogue: name -> (RA deg, Dec deg, visual magnitude).
STARS = {
 "Polaris":(37.95,89.26,1.98), "Dubhe":(165.93,61.75,1.79), "Merak":(165.46,56.38,2.37),
 "Phecda":(178.46,53.69,2.44), "Megrez":(183.86,57.03,3.31), "Alioth":(193.51,55.96,1.76),
 "Mizar":(200.98,54.93,2.23), "Alkaid":(206.89,49.31,1.85), "Caph":(2.29,59.15,2.28),
 "Schedar":(10.13,56.54,2.24), "Navi":(14.18,60.72,2.15), "Ruchbah":(21.45,60.24,2.68), "Segin":(28.60,63.67,3.35),
 "Betelgeuse":(88.79,7.41,.50), "Bellatrix":(81.28,6.35,1.64), "Alnitak":(85.19,-1.94,1.74),
 "Alnilam":(84.05,-1.20,1.69), "Mintaka":(83.00,-.30,2.25), "Saiph":(86.94,-9.67,2.07), "Rigel":(78.63,-8.20,.13),
 "Sirius":(101.29,-16.72,-1.46), "Procyon":(114.83,5.22,.34), "Aldebaran":(68.98,16.51,.85), "Elnath":(81.57,28.61,1.65),
 "Pollux":(116.33,28.03,1.14), "Castor":(113.65,31.89,1.58), "Regulus":(152.09,11.97,1.35), "Denebola":(177.26,14.57,2.14),
 "Spica":(201.30,-11.16,.97), "Arcturus":(213.92,19.18,-.05), "Vega":(279.23,38.78,.03), "Deneb":(310.36,45.28,1.25),
 "Albireo":(292.68,27.96,3.05), "Altair":(297.70,8.87,.77), "Antares":(247.35,-26.43,1.06), "Acrab":(241.36,-19.81,2.56),
 "Dschubba":(240.08,-22.62,2.32), "Shaula":(263.40,-37.10,1.62), "Lesath":(262.69,-37.30,2.70),
 "Kaus Australis":(276.04,-34.38,1.79), "Nunki":(283.82,-26.30,2.05), "Rukbat":(290.66,-40.62,3.97), "Alnasl":(271.45,-30.42,2.98),
 "Acrux":(186.65,-63.10,.77), "Mimosa":(191.93,-59.69,1.25), "Gacrux":(187.79,-57.11,1.59), "Imai":(183.79,-58.75,2.79),
 "Rigil Kent":(219.90,-60.84,-.27), "Hadar":(210.96,-60.37,.61), "Canopus":(95.99,-52.70,-.74),
 "Achernar":(24.43,-57.24,.46), "Fomalhaut":(344.41,-29.62,1.16), "Capella":(79.17,46.00,.08)
}
CONSTELLATIONS = {
 "Ursa Major":[("Dubhe","Merak"),("Merak","Phecda"),("Phecda","Megrez"),("Megrez","Dubhe"),("Megrez","Alioth"),("Alioth","Mizar"),("Mizar","Alkaid")],
 "Cassiopeia":[("Caph","Schedar"),("Schedar","Navi"),("Navi","Ruchbah"),("Ruchbah","Segin")],
 "Orion":[("Betelgeuse","Bellatrix"),("Bellatrix","Mintaka"),("Mintaka","Alnilam"),("Alnilam","Alnitak"),("Alnitak","Saiph"),("Saiph","Rigel"),("Rigel","Mintaka"),("Alnitak","Betelgeuse")],
 "Taurus":[("Aldebaran","Elnath")], "Gemini":[("Castor","Pollux")], "Leo":[("Regulus","Denebola")], "Cygnus":[("Deneb","Albireo")],
 "Scorpius":[("Acrab","Dschubba"),("Dschubba","Antares"),("Antares","Shaula"),("Shaula","Lesath")],
 "Sagittarius":[("Alnasl","Kaus Australis"),("Kaus Australis","Rukbat"),("Kaus Australis","Nunki")],
 "Crux":[("Acrux","Gacrux"),("Mimosa","Imai")], "Centaurus":[("Rigil Kent","Hadar")]
}

def build_sky_figure(object_query, utc_text, output_png=None, dpi=130, watermark_text="ASTRONEOS",
                     watermark_size="medium", reference_name="Observatory", reference_lat=-19.9,
                     reference_lon=-43.9, reference_alt=0, time_mode="UTC", render_size="HD", language="EN",
                     star_magnitude_limit=7.0, trail_positions=None, show_info_panel=True, distance_unit="km", display_time_mode: str | None = None, **_unused):
    t = parse_input_time_for_mode(utc_text, time_mode, reference_lat, reference_lon)
    time_mode = display_time_mode or time_mode
    eph = query_horizons(object_query, t)
    loc = EarthLocation(lat=float(reference_lat)*u.deg, lon=float(reference_lon)*u.deg, height=float(reference_alt)*u.m)
    frame = AltAz(obstime=t, location=loc)
    names = list(STARS)
    stars = SkyCoord(ra=[STARS[n][0] for n in names]*u.deg, dec=[STARS[n][1] for n in names]*u.deg).transform_to(frame)
    pos = {n:(float(stars.az.deg[i]),float(stars.alt.deg[i])) for i,n in enumerate(names)}
    obj = SkyCoord(ra=eph.ra_deg*u.deg, dec=eph.dec_deg*u.deg, distance=eph.delta_au*u.au, frame=GCRS(obstime=t)).transform_to(frame)
    obj_az, obj_alt = float(obj.az.deg), float(obj.alt.deg)
    solar_system = _solar_system_positions(t, loc, frame)
    sun_alt = solar_system["sun"]["alt"]
    mw_visibility = milky_way_visibility(sun_alt)
    figsize,pixel_size = figure_size_from_render_size(render_size,dpi)
    fig=plt.figure(figsize=figsize,dpi=dpi,facecolor="#030711")
    ax=fig.add_axes([.055,.095,.68,.78],projection="polar")
    zenith_color,horizon_color=_sky_colors(sun_alt)
    ax.set_facecolor(zenith_color); ax.set_theta_zero_location("N"); ax.set_theta_direction(1); ax.set_rlim(0,90)
    # Keep the sky plot clean; altitude graduations are intentionally hidden.
    ax.set_rticks([]); ax.set_yticklabels([])
    ax.set_thetagrids([0,90,180,270],["N","E","S","W"],color="#bd6f63",fontsize=10)
    ax.grid(color="#8290a0",alpha=.10,linewidth=.4)
    ax.spines["polar"].set_color("#263342")
    ax.spines["polar"].set_linewidth(.7)

    # Radial atmospheric gradient: darker at the zenith and brighter toward
    # the horizon. Both endpoints evolve continuously with the Sun altitude,
    # avoiding visible jumps between day and twilight classifications.
    ring_edges=np.linspace(0,90,91)
    for bottom in ring_edges[:-1]:
        fraction=((bottom+.5)/90.0)**1.35
        color=zenith_color*(1-fraction)+horizon_color*fraction
        ax.bar(0,1.02,width=2*np.pi,bottom=bottom,color=color,
               alpha=1.0,edgecolor="none",linewidth=0,zorder=.15)

    # Milky Way texture. Points are distributed around the true galactic plane
    # and transformed for this site/time, so the band rotates with the real sky.
    rng=np.random.default_rng(419)
    count=9000
    gal_l=rng.uniform(0,360,count)
    gal_b=np.clip(rng.normal(0,7.5,count),-24,24)
    gal=SkyCoord(l=gal_l*u.deg,b=gal_b*u.deg,frame="galactic").transform_to(frame)
    mask=gal.alt.deg>=0
    mw_theta=np.radians(gal.az.deg[mask]); mw_r=90-gal.alt.deg[mask]
    density=np.exp(-.5*(gal_b[mask]/8.0)**2)
    ax.scatter(mw_theta,mw_r,s=5.5*density+.35,c="#91abc4",alpha=(.012+density*.032)*mw_visibility,
               linewidths=0,zorder=.35)
    core=np.abs(gal_b[mask])<3.2
    ax.scatter(mw_theta[core],mw_r[core],s=11*density[core]+1,c="#c2b89d",
               alpha=(.018+density[core]*.025)*mw_visibility,linewidths=0,zorder=.36)
    # Real stellar background from the compact Hipparcos catalogue. Apparent
    # magnitude is attenuated toward the horizon by a simple airmass model.
    catalog=_load_hipparcos_catalog()
    hip_coords=SkyCoord(ra=catalog["ra"]*u.deg,dec=catalog["dec"]*u.deg,frame="icrs").transform_to(frame)
    hip_alt=np.asarray(hip_coords.alt.deg); hip_az=np.asarray(hip_coords.az.deg)
    apparent=atmospheric_magnitude(catalog["vmag"], hip_alt)
    hip_visibility=star_visibility(catalog["vmag"], hip_alt, sun_alt, float(star_magnitude_limit))
    hm=hip_visibility>0
    htheta=np.radians(hip_az[hm]); hr=90-hip_alt[hm]; hmag=apparent[hm]
    hsizes=np.clip(12.0*10**(-.24*hmag),.22,48.0)
    hcolors=_bv_colors(catalog["bv"][hm])
    bright=hmag<2.3
    if np.any(bright):
        ax.scatter(htheta[bright],hr[bright],s=hsizes[bright]*6.0,c=hcolors[bright],
                   alpha=.075*hip_visibility[hm][bright],linewidths=0,zorder=1.1)
    ax.scatter(htheta,hr,s=hsizes,c=hcolors,alpha=(np.clip(.90-.055*hmag,.38,.95)*hip_visibility[hm] if hmag.size else 0.),
               linewidths=0,zorder=1.3)
    named_visibility = {n: float(star_visibility(STARS[n][2], pos[n][1], sun_alt, float(star_magnitude_limit))) for n in names}
    for cname,segments in CONSTELLATIONS.items():
        points=[]
        for a,b in segments:
            az1,al1=pos[a]; az2,al2=pos[b]
            line_opacity = min(named_visibility[a], named_visibility[b])
            if line_opacity>0:
                ax.plot(np.unwrap(np.radians([az1,az2])),[90-al1,90-al2],color="#6889a6",alpha=.16*line_opacity,linewidth=.48,zorder=2); points += [(az1,al1),(az2,al2)]
    visible=[(n,pos[n][0],pos[n][1],STARS[n][2]) for n in names if named_visibility[n]>0]
    named_alpha=np.array([named_visibility[v[0]] for v in visible])
    sizes=np.clip(34-7*np.array([v[3] for v in visible]),5,46)
    star_theta=np.radians([v[1] for v in visible]); star_r=[90-v[2] for v in visible]
    # Soft halos plus sharp cores give bright stars the photographic appearance
    # seen in planetarium software without changing their calculated positions.
    ax.scatter(star_theta,star_r,s=sizes*3.6,c="#9fc8ff",alpha=(.10*named_alpha if named_alpha.size else 0.),linewidths=0,zorder=3.7)
    warm={"Betelgeuse","Aldebaran","Antares","Arcturus","Pollux"}
    colors=["#ffd0a0" if v[0] in warm else "#eef5ff" for v in visible]
    ax.scatter(star_theta,star_r,s=sizes,c=colors,alpha=(named_alpha if named_alpha.size else 0.),edgecolors="#ffffff",linewidths=.18,zorder=4)
    occupied=[]
    for name,az,alt,mag in sorted(visible,key=lambda item:item[3]):
        radius=90-alt; theta=np.radians(az)
        xy=np.array([radius*np.sin(theta),radius*np.cos(theta)])
        if mag<=1 and all(np.linalg.norm(xy-other)>8 for other in occupied):
            ax.annotate(name,(theta,radius),xytext=(4,3),textcoords="offset points",color="#dce8f5",fontsize=7,alpha=.88*named_visibility[name])
            occupied.append(xy)
    visible_bodies = [(key, body) for key, body in solar_system.items() if body["alt"] >= 0 and (key in ("sun", "moon") or sun_alt < 0)]
    for key, body in visible_bodies:
        body_alpha = 1. if key in ("sun", "moon") else float(np.clip(-sun_alt / 6., 0., 1.))
        theta, radius = np.radians(body["az"]), 90-body["alt"]
        if key == "moon":
            draw_moon(ax, body, solar_system["sun"])
        else:
            ax.scatter([theta],[radius],s=body["size"]*2.8,c=body["color"],alpha=.13*body_alpha,linewidths=0,zorder=4.7)
            ax.scatter([theta],[radius],s=body["size"],c=body["color"],marker=body["marker"],
                       edgecolors="#ffffff",linewidths=.35,alpha=body_alpha,zorder=5.0)
        lang=language.upper()
        body_label = SOLAR_SYSTEM_LABELS_PT[key] if lang == "PT" else (SOLAR_SYSTEM_LABELS_ES[key] if lang == "ES" else body["label"])
        ax.annotate(body_label,(theta,radius),xytext=(6,5),textcoords="offset points",
                    color=body["color"],fontsize=7.5,weight="bold",alpha=.96*body_alpha,zorder=5.2)
    # Perfectly circular geometric horizon at 0 degrees altitude.
    horizon_theta=np.linspace(0,2*np.pi,721)
    circular_horizon=np.full_like(horizon_theta,89.15)
    ax.fill_between(horizon_theta,circular_horizon,90,color="#010204",alpha=.98,zorder=6)
    ax.plot(horizon_theta,circular_horizon,color="#34495c",alpha=.72,linewidth=.7,zorder=6.1)
    below=("abaixo do horizonte" if language.upper()=="PT" else ("bajo el horizonte" if language.upper()=="ES" else "below horizon"))
    if trail_positions:
        horizontal_trail=celestial_trail_to_horizontal(trail_positions,frame)
        visible_path=visible_target_path(obj_az,obj_alt,horizontal_trail)
        if visible_path:
            trail_theta=np.unwrap(np.radians([p[0] for p in visible_path]))
            trail_r=[90-p[1] for p in visible_path]
            ax.plot(trail_theta,trail_r,color="#ffcc33",alpha=.65,linewidth=1.2,
                    linestyle="--",zorder=8)
            # The current position has its own target marker below. Plot only
            # historical samples here to avoid a doubled, visually offset dot.
            if len(trail_theta)>1:
                ax.scatter(trail_theta[:-1],trail_r[:-1],s=10,color="#ffcc33",
                           alpha=.52,linewidths=0,zorder=8.2)
    if obj_alt>=0:
        r=90-obj_alt
        theta=np.radians(obj_az)
        ax.scatter([theta],[r],s=150,marker="o",facecolors="none",
                   edgecolors="#ffcc33",linewidths=1.5,zorder=10)
        ax.scatter([theta],[r],s=18,marker="o",color="#ffcc33",
                   edgecolors="#241d00",linewidths=.45,zorder=10.1)
    # Keep the plotted sky clean: the marker identifies the target and its data
    # live in a separate information panel outside the horizon circle.
    shown,label=format_time_for_map(t,time_mode,reference_lat,reference_lon)
    km=getattr(eph,"distance_km",eph.delta_au*AU_KM)
    v="—" if eph.vmag is None else format_number(eph.vmag,2,language,False)
    lang=language.upper(); pt=lang=="PT"; es=lang=="ES"
    title="Céu no horário selecionado" if pt else ("Cielo en la hora seleccionada" if es else "Sky at selected time")
    dist="Distância" if pt else ("Distancia" if es else "Distance")
    alt_label="Altitude" if pt else ("Altitud" if es else "Altitude")
    az_label="Azimute" if pt else ("Acimut" if es else "Azimuth")
    status=target_status(sun_alt,obj_alt,eph.vmag,language)
    ax.set_title(f"{title}\n{shown} {label}",color="white",fontsize=12,weight="bold",pad=22)
    import textwrap
    status=textwrap.fill(status,width=25)
    panel=(f"{'OBJETO' if (pt or es) else 'TARGET'}\n{eph.targetname}\n\n"
           f"{alt_label}   {format_number(obj_alt,1,language,False)}°\n{az_label}   {format_number(obj_az,1,language,False)}°\n"
           f"{dist}   {figure_distance(fig, km, distance_unit, language)}\n{Translator(language).tr('Magnitude')} V   {v}\n\n"
           f"{status}\n\n{'LOCAL' if (pt or es) else 'SITE'}\n{reference_name}\n"
           f"{format_number(reference_lat,4,language,False)}°, {format_number(reference_lon,4,language,False)}°")
    if show_info_panel:
        fig.text(.775,.70,panel,ha="left",va="top",color="#e7eef7",fontsize=10.5,linespacing=1.45,
                 bbox=dict(boxstyle="round,pad=.8",facecolor="#0b1521",edgecolor="#29425b",linewidth=1.0,alpha=.98))
        if obj_alt>=0:
            target_legend="⊙  Posição do objeto" if pt else ("⊙  Posición del objeto" if es else "⊙  Target position")
            fig.text(.775,.16,target_legend,color="#ffcc33",fontsize=10,weight="bold")
    fig.text(.018,.035,APP_TITLE,color="white",alpha=.65,fontsize=9,weight="bold")
    add_watermark(fig,watermark_text,watermark_size)
    result={"targetname":eph.targetname,"utc":eph.utc_iso,"display_time":shown,"display_label":label,"geo_km":km,"vmag":eph.vmag,"current_altitude":obj_alt,"current_azimuth":obj_az,"current_ra_deg":float(eph.ra_deg),"current_dec_deg":float(eph.dec_deg),"sun_altitude":sun_alt,"solar_system":solar_system,"map_type":"sky","best_altitude":obj_alt,"best_altitude_display_time":shown,"best_altitude_display_label":label,"best_altitude_reason":"selected_time","suggested_filename":suggest_output_filename(object_query,utc_text,eph.targetname),"output":output_png,"pixel_size":pixel_size}
    if output_png:
        path=Path(output_png); path.parent.mkdir(parents=True,exist_ok=True); fig.savefig(path,dpi=dpi,facecolor=fig.get_facecolor()); result["output"]=str(path)
    return fig,result
