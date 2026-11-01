"""Lebanon Is Burning - MSBA 325 wildfire dashboard (Streamlit + Plotly)."""
import base64
import json
import os
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Lebanon Is Burning", page_icon="🔥", layout="wide")

from pathlib import Path

APP_DIR = Path(__file__).resolve().parent


def P(name):
    """Find a data file whether it sits in data/ or next to app.py (e.g. if the folder was flattened on upload)."""
    for c in (APP_DIR / "data" / name, APP_DIR / name):
        if c.exists():
            return c
    st.error(f"Data file not found: {name}. Upload it to the repository's data folder (or next to app.py).")
    st.stop()


# ---------- design tokens (reference palette, light mode) ----------
INK, INK2, MUTED = "#F2EEE8", "#C9C4BC", "#8C877F"
GRID, AXIS, SURFACE = "#2A2E36", "#3A3F48", "#171A20"
FIRE, OTHER = "#FF6A2B", "#4C6EF5"            # categorical slots 2 and 1
FIRE_RAMP = ["#2a1a14", "#5a2a17", "#8f3a17", "#c94d1f", "#eb6834", "#ff8a4c", "#ffc199"]  # one hue, light->dark
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
FONT = "Inter, system-ui, -apple-system, Segoe UI, sans-serif"


def style(fig, h=380):
    fig.update_layout(
        height=h, margin=dict(l=8, r=8, t=36, b=8), paper_bgcolor=SURFACE, plot_bgcolor=SURFACE,
        font=dict(family=FONT, color=INK2, size=13), title_font=dict(color=INK, size=15),
        hoverlabel=dict(bgcolor="#0E1013", font_color=INK, bordercolor=AXIS), legend=dict(orientation="h", yanchor="top", y=-0.12, x=0),
    )
    fig.update_xaxes(showgrid=False, linecolor=AXIS, tickfont_color=MUTED, title_font_color=INK2)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, linecolor=AXIS, tickfont_color=MUTED, title_font_color=INK2)
    return fig


@st.cache_data
def load():
    f = pd.read_csv(P("fires_viirs_2012_2025.csv"), parse_dates=["acq_date"])
    w = pd.read_csv(P("weather_daily_2012_2025.csv"), parse_dates=["date"])
    loss = pd.read_csv(P("forest_loss_national.csv"))
    loss_d = pd.read_csv(P("forest_loss_districts.csv"))
    loss_e = pd.read_csv(P("forest_loss_estimates.csv"))
    geo = json.load(open(P("districts.geojson")))
    border = json.load(open(P("lebanon_border.geojson")))
    stations = pd.read_csv(P("fire_stations.csv"))
    icon = "data:image/png;base64," + base64.b64encode(open(P("station_icon.png"), "rb").read()).decode()
    return f, w, loss, loss_d, loss_e, geo, border, stations, icon


fires, weather, loss_nat, loss_dist, loss_est, geo, geo_border, stations, ICON = load()


def station_layers(half_h=0.055):
    """One Civil Defence badge per fire station, pinned to its location (square image)."""
    half_w = half_h / 0.83                     # round badge; 0.83 = cos(34 deg) keeps it round at Lebanon's latitude
    return [dict(sourcetype="image", source=ICON,
                 coordinates=[[r.longitude - half_w, r.latitude + half_h], [r.longitude + half_w, r.latitude + half_h],
                              [r.longitude + half_w, r.latitude - half_h], [r.longitude - half_w, r.latitude - half_h]])
            for r in stations.itertuples()]


def station_hover():
    """Invisible markers on top of the emblems so hovering shows the station name."""
    return go.Scattermap(lat=stations.latitude, lon=stations.longitude, mode="markers", name="Fire station",
                         marker=dict(size=22, color="rgba(0,0,0,0)"), customdata=stations[["name", "district"]],
                         hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]} district<extra>Fire station</extra>")
area = {ft["properties"]["district"]: ft["properties"]["area_sqkm"] for ft in geo["features"]}


# ---------- page styling (Ember Night) ----------
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
html,body,.stApp,.stApp p,.stApp label,.stApp button,.stApp input{font-family:'Inter',system-ui,sans-serif}
.stApp,[data-testid="stAppViewContainer"]{background:#0E1013;color:#ECE8E1;overflow-x:hidden}
[data-testid="stHeader"]{display:none}
.block-container{padding-top:0 !important;max-width:100% !important;padding-left:2.5rem !important;padding-right:2.5rem !important}
.stApp p,.stApp label,.stApp span,.stApp li,.stApp h2,.stApp h3{color:#ECE8E1}
.stApp [data-testid="stCaptionContainer"] p{color:#9a948b}
.stApp [data-baseweb="select"] div,.stApp [data-testid="stPopover"] button{background-color:rgba(23,26,32,.92) !important;border-color:#2A2E36 !important;color:#ECE8E1 !important}
[data-baseweb="popover"] *,[data-testid="stPopoverBody"]{background-color:#171A20;color:#ECE8E1}
.stApp [data-testid="stDataFrame"]{filter:invert(.92) hue-rotate(180deg)}
.stSlider [role="slider"]{background-color:#FF6A2B !important}
div[data-testid="stMetric"]{background:#171A20;border:1px solid #2A2E36;border-left:4px solid #FF6A2B;border-radius:14px;padding:14px 18px}
/* full-bleed hero */
.st-key-hero{width:100vw !important;max-width:100vw !important;position:relative;left:50%;margin-left:-50vw;margin-top:-2rem}
.st-key-hero [data-testid="stPlotlyChart"]{border-bottom:1px solid #2A2E36}
.st-key-hero .updatemenu-button rect{rx:18px;ry:18px}
.st-key-hero .updatemenu-button text{font-weight:700 !important}
/* filter chips floating over the top-right of the map */
.st-key-filters{position:relative;z-index:30;width:min(780px,60vw);margin-left:auto;top:14px;margin-bottom:-74px}
[data-testid="stMainBlockContainer"]{padding-top:0 !important}
.st-key-filters [data-testid="stHorizontalBlock"]{gap:10px}
/* overlay text on the map */
.hero-ov{position:relative;z-index:5;pointer-events:none;height:680px;margin-top:-696px;padding:56px 0 0 48px;font-family:'Inter',sans-serif}
.hero-ov .tag{display:inline-block;background:rgba(255,106,43,.15);color:#ffb28c;border:1px solid rgba(255,106,43,.45);border-radius:99px;padding:4px 13px;font-size:13px;letter-spacing:1.5px}
.hero-ov .h1{font-family:'Inter',sans-serif;font-size:64px;line-height:1.0;margin:16px 0 12px;font-weight:900;color:#F5F2EE !important;letter-spacing:-1.5px}
.hero-ov .h1 .hot{color:#FF6A2B !important}
.hero-ov p.sub{font-size:17px;color:#d8cfc6 !important;margin:0;max-width:480px;line-height:1.35}
.kgrid{position:absolute;left:48px;bottom:30px;display:grid;grid-template-columns:repeat(4,190px);gap:12px}
.kc{background:rgba(23,26,32,.86);backdrop-filter:blur(6px);border:1px solid #2A2E36;border-left:4px solid #FF6A2B;border-radius:12px;padding:12px 16px}
.kc .l{font-size:12px;color:#B9B3AA !important}.kc .v{font-size:28px;font-weight:800;color:#fff !important;line-height:1.2}.kc .s{font-size:12px;color:#FF9a6b !important}
.legend{position:absolute;right:28px;bottom:86px;background:rgba(23,26,32,.88);border:1px solid #2A2E36;border-radius:10px;padding:10px 14px;font-size:12px;width:190px}
.legend .bar{height:8px;border-radius:4px;background:linear-gradient(90deg,#2840ff,#00c8ff,#00d25a,#ffe000,#ff8c00,#e61414);margin:7px 0 3px}
.stTabs [data-baseweb="tab-list"]{gap:10px;margin-top:14px}
.stTabs [data-baseweb="tab"]{border:1px solid #3A3F48 !important;border-radius:99px !important;padding:6px 18px !important;height:auto !important;background:transparent !important}
.stTabs [data-baseweb="tab"][aria-selected="true"]{background:#FF6A2B !important;border-color:#FF6A2B !important}
.stTabs [data-baseweb="tab"][aria-selected="true"] p{color:#111 !important;font-weight:700}
.stTabs [data-baseweb="tab-highlight"],.stTabs [data-baseweb="tab-border"]{display:none}
.st-key-livechip{background:rgba(23,26,32,.92);border:1px solid #2A2E36;border-radius:8px;padding:7px 12px 3px;height:42px}
.st-key-livechip label p{font-weight:800;letter-spacing:1px;color:#ff4d4d !important}
.hero-ov .tag.live{background:rgba(230,20,20,.18);border-color:rgba(255,77,77,.6);color:#ffb3b3}
.hero-ov .tag .dot{display:inline-block;width:9px;height:9px;border-radius:50%;background:#ff3b3b;margin-right:8px;box-shadow:0 0 0 0 rgba(255,59,59,.7);animation:pulse 1.6s infinite}
@keyframes pulse{0%{box-shadow:0 0 0 0 rgba(255,59,59,.7)}70%{box-shadow:0 0 0 10px rgba(255,59,59,0)}100%{box-shadow:0 0 0 0 rgba(255,59,59,0)}}
.ld{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:5px;vertical-align:-1px}
</style>""", unsafe_allow_html=True)

# ---------- filters: slim chips floating over the map ----------
govs = sorted(fires.governorate.dropna().unique())
with st.container(key="filters"):
    c1, c2, c3, c4 = st.columns([1, 1.25, 1, 0.72])
    _y = st.session_state.get("years", (2012, 2025))
    with c1.popover(f"📅  {_y[0]} – {_y[1]}", use_container_width=True):
        yr = st.slider("Years", 2012, 2025, (2012, 2025), key="years")
    gsel = c2.multiselect("Governorates", govs, default=[], placeholder="All governorates", label_visibility="collapsed")
    with c3.popover("⚙  Map options", use_container_width=True):
        mode = st.radio("Map shows", ["Animation 2012 → 2025", "One whole year"], key="yy_mode")
        pick = st.selectbox("Year", list(range(yr[1], yr[0] - 1, -1)), key="yy_year") if mode.startswith("One") else None
        secs = st.slider("Seconds per year", 6, 12, 8, key="yy_secs") if not mode.startswith("One") else 8
        wvar = st.radio("Weather at the 5 stations", ["Off", "Temperature vs normal", "Rainfall vs normal"], key="yy_w")
        show_st2 = st.toggle("Show fire stations", value=False, key="st_sat")
    with c4.container(key="livechip"):
        live = st.toggle("LIVE", value=False, key="live", help="Show NASA fire detections from the last 30 days")

d = fires[fires.year.between(*yr) & fires.governorate.isin(gsel or govs)]
if d.empty:
    st.warning("No fires match these filters.")
    st.stop()

per_year = d.groupby("year").size()
by_dist = d.groupby("district").size().sort_values(ascending=False)
fl = loss_nat[loss_nat.year.between(*yr)]

GRAD = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAlgAAAAECAYAAABStUF5AAAAdElEQVR4nO3WwQ2AIBAEQLQAY2L/vdmJNqCieKAhMx+QWw/4MUzzsqZrW6aey5zVjtbvZu/8W/M7olaSi5hHZkvqT9ci87UyJdmWvUrGr3u1yLzp/XReK9vj2dy/jz3+fLYm9x8TAAChPLAAAIJ5YAEABNsBECXgObyvvZoAAAAASUVORK5CYII="  # dark fade behind the hero text
HEAT = [[0, "rgba(0,0,255,0)"], [0.08, "rgba(40,60,255,0.35)"], [0.25, "rgba(0,200,255,0.55)"],
        [0.45, "rgba(0,210,90,0.65)"], [0.65, "rgba(255,230,0,0.75)"], [0.82, "rgba(255,140,0,0.85)"],
        [1, "rgba(230,20,20,0.95)"]]
MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
LABEL_POS = {"Akkar": "middle right", "Batroun": "middle left", "Metn": "top left",
             "Chouf": "bottom left", "Zahle (Bekaa)": "middle right"}


@st.cache_data(show_spinner="Building the map animation…", max_entries=8)
def hero_figure(yr, gsel, wsel, secs, mode, pick, show_st, no_tiles):
    is_temp, w_on = wsel.startswith("Temp"), wsel != "Off"
    dd = fires[fires.year.between(*yr) & fires.governorate.isin(list(gsel) or govs)].copy()
    DIV = [[0, "#1c5cab"], [0.25, "#6da7ec"], [0.5, "#d9d8d2"], [0.75, "#ec835a"], [1, "#d03b3b"]]
    if not is_temp:
        DIV = [[0, DIV[4][1]], [0.25, DIV[3][1]], [0.5, DIV[2][1]], [0.75, DIV[1][1]], [1, DIV[0][1]]]

    def station_traces(sy, acol, lim, unit):
        out = [dict(type="scattermap", lat=sy.lat.tolist(), lon=sy.lon.tolist(), mode="markers",
                    marker=dict(size=26, color="white"), hoverinfo="skip"),
               dict(type="scattermap", lat=sy.lat.tolist(), lon=sy.lon.tolist(), mode="markers",
                    marker=dict(size=21, color=sy[acol].tolist(), colorscale=DIV, cmin=-lim, cmax=lim, showscale=False),
                    customdata=sy[["site", "temp", "rain", "temp_anom", "rain_anom"]].values.tolist(),
                    hovertemplate="<b>%{customdata[0]}</b><br>Avg max temp %{customdata[1]:.1f}°C "
                                  "(%{customdata[3]:+.1f}°C vs normal)<br>Rain %{customdata[2]:.0f} mm "
                                  "(%{customdata[4]:+.0f} " + unit + " vs normal)<extra></extra>")]
        for site, pos in LABEL_POS.items():
            r = sy[sy.site == site]
            name = site.replace(" (Bekaa)", "")
            txt = [f"{name} {v:+.1f}°C" if is_temp else f"{name} {v:+.0f} {unit} rain" for v in r[acol]]
            txt = [f"   {t}" if "right" in pos else f"{t}   " for t in txt]
            out.append(dict(type="scattermap", lat=r.lat.tolist(), lon=r.lon.tolist(), mode="markers+text",
                            textposition=pos, text=txt, marker=dict(size=26, color="rgba(0,0,0,0)"),
                            hoverinfo="skip", textfont=dict(color="white", size=13)))
        return out

    def heat(pts, zmax):
        return dict(type="densitymap", lat=pts.latitude.tolist(), lon=pts.longitude.tolist(), radius=16,
                    colorscale=HEAT, zmin=0, zmax=zmax, zauto=False, showscale=False, hoverinfo="skip")

    frames, menus, sliders = [], [], []
    if mode.startswith("One"):
        fy = dd[dd.year == pick]
        wy = (weather.assign(year=weather.date.dt.year).groupby(["year", "site"])
              .agg(temp=("temp_max_c", "mean"), rain=("precip_mm", "sum"),
                   lat=("latitude", "first"), lon=("longitude", "first")).reset_index())
        wy["temp_anom"] = wy.temp - wy.groupby("site").temp.transform("mean")
        wy["rain_anom"] = 100 * (wy.rain / wy.groupby("site").rain.transform("mean") - 1)
        acol = "temp_anom" if is_temp else "rain_anom"
        sy = wy[wy.year == pick]
        data = [heat(fy, max(3.0, 0.006 * len(fy))),
                dict(type="scattermap", lat=fy.latitude.tolist(), lon=fy.longitude.tolist(), mode="markers",
                     marker=dict(size=5, color="#ffe066", opacity=0.9),
                     customdata=fy[["district", "acq_date"]].astype(str).values.tolist(),
                     hovertemplate="Fire in %{customdata[0]}<br>%{customdata[1]}<extra></extra>")] + \
               (station_traces(sy, acol, float(wy[acol].abs().max()), "%") if w_on else [])
        tm, rm = sy.temp_anom.mean(), sy.rain_anom.mean()
        title = (f"<span style='font-size:34px'><b>{pick}</b></span><br>{len(fy):,} fires · "
                 f"{'hotter' if tm > 0 else 'cooler'} than normal ({tm:+.1f}°C) · rain {rm:+.0f}% vs normal")
    else:
        # weather by month
        wm = (weather.assign(year=weather.date.dt.year, month=weather.date.dt.month)
              .groupby(["year", "month", "site"])
              .agg(temp=("temp_max_c", "mean"), rain=("precip_mm", "sum"),
                   lat=("latitude", "first"), lon=("longitude", "first")).reset_index())
        wm["temp_anom"] = wm.temp - wm.groupby(["site", "month"]).temp.transform("mean")
        wm["rain_anom"] = wm.rain - wm.groupby(["site", "month"]).rain.transform("mean")
        acol = "temp_anom" if is_temp else "rain_anom"
        lim = float(wm[acol].abs().quantile(0.98))
        years = list(range(yr[0], yr[1] + 1))
        dd["t"] = dd.year * 12 + dd.month - 1
        origin = pd.Timestamp(yr[0], 1, 1)
        dd["day"] = (dd.acq_date - origin).dt.days
        cnt = dd.groupby("t").size()
        zmax = max(3.0, 0.008 * max(1, len(dd) / len(years)))
        n_days = (pd.Timestamp(yr[1], 12, 31) - origin).days
        STEP, FADE = 7, 42              # one frame per week; each fire glows then fades over 6 weeks
        lat, lon, day = dd.latitude.values, dd.longitude.values, dd.day.values
        dist_, date_ = dd.district.astype(str).values, dd.acq_date.dt.strftime("%d %b %Y").values

        def dots(D):
            age = D - day
            k = (age >= 0) & (age < FADE)
            a = age[k]
            size = (4 + 9 * np.exp(-a / 6)).round(1).tolist()
            op = (0.18 + 0.82 * np.exp(-a / 12)).round(2).tolist()
            col = np.where(a < 7, "#fff3a0", np.where(a < 21, "#ffb000", "#ff5a1a")).tolist()
            return dict(type="scattermap", lat=lat[k].tolist(), lon=lon[k].tolist(), mode="markers",
                        marker=dict(size=size, color=col, opacity=op),
                        customdata=np.c_[dist_[k], date_[k]].tolist(),
                        hovertemplate="Fire in %{customdata[0]}<br>%{customdata[1]}<extra></extra>")

        def month_parts(T):
            y, m = divmod(T, 12)
            last12 = dd[(dd.t > T - 12) & (dd.t <= T)]
            sy = wm[(wm.year == y) & (wm.month == m + 1)]
            tm = sy.temp_anom.mean()
            sub = (f"{int(cnt.get(T, 0)):,} fires this month · {len(last12):,} in the last 12 months · "
                   f"{'hotter' if tm > 0 else 'cooler'} than a normal {MONTH_NAMES[m]} ({tm:+.1f}°C)")
            return heat(last12, zmax), (station_traces(sy, acol, lim, "mm") if w_on else []), sub

        n_tr = 2 + ((2 + len(LABEL_POS)) if w_on else 0)
        prevT, sub, steps = None, "", []
        for k, D in enumerate(range(0, n_days + 1, STEP)):
            date = origin + pd.Timedelta(days=D)
            T = date.year * 12 + date.month - 1
            ttl_head = f"<span style='font-size:34px'><b>{MONTH_NAMES[date.month - 1]} {date.year}</b></span><br>"
            if T != prevT:
                h, stn, sub = month_parts(T)
                fr = dict(name=str(k), data=[h, dots(D)] + stn, traces=list(range(n_tr)),
                          layout=dict(title=dict(text=ttl_head + sub)))
                steps.append(dict(label=str(date.year) if date.month == 1 else "", method="animate",
                                  args=[[str(k)], dict(mode="immediate", frame=dict(duration=0, redraw=True),
                                                       transition=dict(duration=0))]))
                prevT = T
            else:
                fr = dict(name=str(k), data=[dots(D)], traces=[1], layout=dict(title=dict(text=ttl_head + sub)))
            frames.append(fr)
        # before Play: the whole period at a glance (all fires as one heat glow); Play then runs week by week
        data = [heat(dd, max(3.0, 0.004 * len(dd))), dict(type="scattermap", lat=[], lon=[], mode="markers")] + frames[0]["data"][2:]
        title = (f"<span style='font-size:34px'><b>{yr[0]}–{yr[1]}</b></span><br>{len(dd):,} fires · press Play to watch them "
                 "spread week by week")
        ms = int(secs * 1000 * STEP / 365)
        menus = [dict(type="buttons", direction="left", x=0.031, y=0.49, xanchor="left", yanchor="top",
                      pad=dict(r=10, t=0, l=0), showactive=False, bgcolor="#FF6A2B", bordercolor="#FF6A2B",
                      font=dict(color="#111111", size=15, family="Inter, sans-serif"),
                      buttons=[dict(label=f"▶  Play {yr[0]} → {yr[1]}", method="animate",
                                    args=[None, dict(frame=dict(duration=ms, redraw=True),
                                                     transition=dict(duration=0), fromcurrent=True)]),
                               dict(label="❚❚  Pause", method="animate",
                                    args=[[None], dict(frame=dict(duration=0, redraw=False),
                                                       mode="immediate", transition=dict(duration=0))])])]
        sliders = [dict(active=0, x=0.645, len=0.335, y=0.025, yanchor="bottom", pad=dict(t=0, b=0),
                        currentvalue=dict(visible=False), ticklen=3, minorticklen=0, bgcolor="#2A2E36",
                        activebgcolor="#FF6A2B", bordercolor="#3A3F48", font=dict(color="#C9C4BC", size=11),
                        tickcolor="#5c5852", steps=steps)]

    if show_st:
        data = data + [dict(type="scattermap", lat=stations.latitude.tolist(), lon=stations.longitude.tolist(),
                            mode="markers", marker=dict(size=22, color="rgba(0,0,0,0)"),
                            customdata=stations[["name", "district"]].values.tolist(),
                            hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]} district<extra>Fire station</extra>")]
    layers = ([] if no_tiles else [
        dict(sourcetype="raster", below="traces", sourceattribution="Imagery © Esri, Maxar, Earthstar Geographics",
             source=["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"]),
        dict(sourcetype="raster", below="traces",
             source=["https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}"])]) + [
        dict(source=geo_border, type="line", color="#ff4d4d", line=dict(width=2.5, dash=[2, 1.5]), below="traces")
    ] + (station_layers(0.045) if show_st else [])
    layout = dict(
        height=680, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="#0E1013", showlegend=False,
        font=dict(family=FONT, color="#ECE8E1"),
        title=dict(text=title, x=0.031, xanchor="left", y=0.395, yanchor="top", yref="paper",
                   font=dict(size=15, color="#ECE8E1")),
        hoverlabel=dict(bgcolor="#0E1013", font_color="#ECE8E1"),
        updatemenus=menus, sliders=sliders,
        images=[dict(source=GRAD, xref='paper', yref='paper', x=0, y=1, sizex=0.5, sizey=1, sizing='stretch', layer='above', xanchor='left', yanchor='top')],
        map=dict(style="white-bg", center={"lat": 33.86, "lon": 35.25}, zoom=7.7, layers=layers))
    return dict(data=data, layout=layout, frames=frames)


LIVE_DAYS = 30                               # live mode always shows the 30 days up to the moment the app is opened
# ---------- LIVE MODE: recent fires from NASA FIRMS (near real time) ----------
from datetime import datetime, timezone, timedelta
import io
import urllib.request
from shapely.geometry import shape, Point
from shapely.prepared import prep

LEB_BBOX = "35.05,33.0,36.7,34.75"          # west,south,east,north
FIRMS_SOURCES = ["VIIRS_SNPP_NRT", "VIIRS_NOAA20_NRT", "VIIRS_NOAA21_NRT"]
BEIRUT = timezone(timedelta(hours=2))
EMPTY_LIVE = pd.DataFrame({"latitude": pd.Series(dtype=float), "longitude": pd.Series(dtype=float),
                           "frp": pd.Series(dtype=float), "when": pd.Series(dtype="datetime64[ns, UTC]"),
                           "district": pd.Series(dtype=object), "age_h": pd.Series(dtype=float), "sensor": pd.Series(dtype=object)})        # Lebanon winter time (UTC+2); summer is UTC+3


@st.cache_resource
def district_shapes():
    return [(ft["properties"]["district"], prep(shape(ft["geometry"]))) for ft in geo["features"]]


def where_is(lat, lon):
    p = Point(lon, lat)
    for name, poly in district_shapes():
        if poly.contains(p):
            return name
    return None


@st.cache_data(ttl=600, show_spinner="Fetching the latest satellite detections from NASA FIRMS…")
def fetch_live(days):
    """Pull the last `days` days of VIIRS detections over Lebanon (all three satellites). Refreshes every 10 min."""
    if os.environ.get("LIVE_SAMPLE"):                       # offline preview: replay a real past week as if it were now
        s = fires[(fires.acq_date >= "2025-10-12") & (fires.acq_date <= "2025-11-11")].copy()
        s["sensor"] = "VIIRS S-NPP"
        t0 = s.acq_date.max() + pd.Timedelta(hours=int(s[s.acq_date == s.acq_date.max()].acq_time.max()) // 100)
        now = (t0 + pd.Timedelta(hours=2, minutes=40)).tz_localize("UTC").to_pydatetime()
    else:
        try:
            key = st.secrets["FIRMS_MAP_KEY"]
        except Exception:
            key = os.environ.get("FIRMS_MAP_KEY", "")
        if not key:
            return None, "No NASA FIRMS key found. Add FIRMS_MAP_KEY to the app's Secrets."
        # FIRMS returns at most 10 days per request, so longer windows are fetched in 10-day chunks
        today = datetime.now(timezone.utc).date()
        if days <= 10:
            chunks = [f"{days}"]
        else:
            first = today - timedelta(days=days - 1)
            chunks = [f"{min(10, days - i)}/{first + timedelta(days=i)}" for i in range(0, days, 10)]
        parts, problems, answered = [], [], 0
        for src in FIRMS_SOURCES:
            for ch in chunks:
                url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/{src}/{LEB_BBOX}/{ch}"
                try:
                    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "lebanon-wildfires-app"}), timeout=30) as r:
                        txt = r.read().decode("utf-8", "replace")
                except Exception as e:
                    problems.append(f"{src}: {type(e).__name__}")
                    continue
                if not txt.lstrip().startswith("latitude"):            # FIRMS answers errors as plain text
                    problems.append(f"{src}: {txt.strip()[:120].replace(key, '***')}")
                    continue
                answered += 1
                x = pd.read_csv(io.StringIO(txt))
                if len(x):
                    parts.append(x.assign(sensor=src.replace("_NRT", "").replace("_", " ")))
        if answered == 0:
            return None, "NASA FIRMS did not return any data. " + (" | ".join(dict.fromkeys(problems))[:400] if problems else "")
        if not parts:                                                   # NASA answered: simply no fires in the window
            return EMPTY_LIVE.copy(), datetime.now(timezone.utc)
        s = pd.concat(parts, ignore_index=True).drop_duplicates(["latitude", "longitude", "acq_date", "acq_time", "sensor"])
        s["acq_date"] = pd.to_datetime(s["acq_date"])
        now = datetime.now(timezone.utc)
    t = s["acq_time"].astype(int)
    s["when"] = (pd.to_datetime(s["acq_date"]) + pd.to_timedelta(t // 100, "h") + pd.to_timedelta(t % 100, "m")).dt.tz_localize("UTC")
    s = s[s["when"] >= now - timedelta(days=days)]
    s["district"] = [where_is(a, b) for a, b in zip(s.latitude, s.longitude)]
    s = s[s.district.notna()].copy()                          # keep detections inside Lebanon only
    if s.empty:
        return EMPTY_LIVE.copy(), now
    s["age_h"] = (now - s["when"]).dt.total_seconds() / 3600
    return s.sort_values("when"), now


def ago(h):
    return f"{h * 60:.0f} min ago" if h < 1 else (f"{h:.0f} h ago" if h < 48 else f"{h / 24:.0f} days ago")


def age_bands(days):
    """Colour bands for dot age: hours for short windows, days for long ones."""
    return (6, 24, "&lt; 6 h", "6–24 h", "older") if days <= 2 else (24, 168, "&lt; 24 h", "1–7 days", "older")


def live_figure(s, no_tiles, days):
    layers = ([dict(sourcetype="image", source=PREV, coordinates=PREV_COORDS, below="traces")] if "PREV" in globals() and no_tiles else
              [] if no_tiles else [
        dict(sourcetype="raster", below="traces", sourceattribution="Imagery © Esri, Maxar, Earthstar Geographics",
             source=["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"]),
        dict(sourcetype="raster", below="traces",
             source=["https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}"])]) + [
        dict(source=geo_border, type="line", color="#ff4d4d", line=dict(width=2.5, dash=[2, 1.5]), below="traces")]
    a1, a2 = age_bands(days)[:2]
    col = np.where(s.age_h < a1, "#fff3a0", np.where(s.age_h < a2, "#ffb000", "#ff5a1a"))
    size = 9 + 10 * np.clip(np.log1p(s.frp.fillna(1)) / 4, 0, 1.4)
    hover = [f"<b>{dd}</b><br>{w.astimezone(BEIRUT):%a %d %b, %H:%M} Beirut time · {ago(a)}<br>Intensity {f:,.1f} MW · {sn}"
             for dd, w, a, f, sn in zip(s.district, s["when"], s.age_h, s.frp.fillna(0), s.sensor)]
    data = [
        go.Scattermap(lat=s.latitude, lon=s.longitude, mode="markers", hoverinfo="skip",      # soft halo
                      marker=dict(size=size * 3.2, color=col, opacity=0.18)),
        go.Scattermap(lat=s.latitude, lon=s.longitude, mode="markers", text=hover, hovertemplate="%{text}<extra></extra>",
                      marker=dict(size=size, color=col, opacity=0.95))]
    fig = go.Figure(data)
    fig.update_layout(height=680, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="#0E1013", showlegend=False,
                      font=dict(family=FONT, color="#ECE8E1"), hoverlabel=dict(bgcolor="#0E1013", font_color="#ECE8E1"),
                      images=[dict(source=GRAD, xref='paper', yref='paper', x=0, y=1, sizex=0.5, sizey=1, sizing='stretch',
                                   layer='above', xanchor='left', yanchor='top')],
                      map=dict(style="white-bg", center={"lat": 33.86, "lon": 35.25}, zoom=7.7, layers=layers))
    return fig


def render_live():
    s, now = fetch_live(LIVE_DAYS)
    if s is None:
        fetch_live.clear()                                   # don't keep a failed request cached; retry on next click
        st.error(now)
        return
    if gsel:                                                  # respect the governorate filter
        g_of = {ft["properties"]["district"]: ft["properties"]["governorate"] for ft in geo["features"]}
        s = s[s.district.map(g_of).isin(gsel)]
    last24 = s[s.age_h <= 24]
    top = s.district.value_counts()
    latest = s.iloc[-1] if len(s) else None
    strongest = s.loc[s.frp.idxmax()] if len(s) and s.frp.notna().any() else None
    win = {1: "24 hours", 2: "48 hours", 7: "7 days", 30: "30 days"}[LIVE_DAYS]
    b1, b2, b3 = age_bands(LIVE_DAYS)[2:]
    with st.container(key="hero"):
        st.plotly_chart(live_figure(s, bool(os.environ.get("NO_TILES")), LIVE_DAYS), width="stretch",
                        config={"displayModeBar": False, "scrollZoom": True}, key="live_map")
        st.markdown(f"""<div class="hero-ov">
<div class="tag live"><span class="dot"></span>LIVE · NASA FIRMS · updated {now.astimezone(BEIRUT):%H:%M} Beirut time</div>
<div class="h1">Lebanon Is<br><span class="hot">Burning</span></div>
<p class="sub">{len(s):,} fire detections across Lebanon in the last {win}, straight from NASA's satellites.</p>
<div class="kgrid">
 <div class="kc"><div class="l">Fires in the last 24 h</div><div class="v">{len(last24):,}</div><div class="s">{len(s):,} in the last {win}</div></div>
 <div class="kc"><div class="l">Most active district</div><div class="v">{top.index[0] if len(top) else "None"}</div><div class="s">{f"{top.iloc[0]:,} detections" if len(top) else "no fires detected"}</div></div>
 <div class="kc"><div class="l">Latest detection</div><div class="v">{ago(latest.age_h) if latest is not None else "–"}</div><div class="s">{f"{latest.district} · {latest['when'].astimezone(BEIRUT):%a %H:%M}" if latest is not None else ""}</div></div>
 <div class="kc"><div class="l">Strongest fire</div><div class="v">{f"{strongest.frp:,.0f} MW" if strongest is not None else "–"}</div><div class="s">{f"{strongest.district} · radiative power" if strongest is not None else ""}</div></div>
</div>
<div class="legend" style="width:auto;white-space:nowrap">Detected<div style="display:flex;gap:12px;margin-top:8px;align-items:center">
<span><span class="ld" style="background:#fff3a0"></span>{b1}</span><span><span class="ld" style="background:#ffb000"></span>{b2}</span><span><span class="ld" style="background:#ff5a1a"></span>{b3}</span></div>
<div style="margin-top:6px;color:#B9B3AA">Bigger dot = more intense</div></div>
</div>""", unsafe_allow_html=True)
    st.caption(f"Live mode shows every VIIRS fire detection over Lebanon from the last {win} (Suomi-NPP, NOAA-20 and NOAA-21 satellites). "
               "NASA publishes detections about 3 hours after each satellite pass, so 'live' means within a few hours. "
               "Data refreshes every 10 minutes. Some hot spots can be industrial heat or agricultural burning.")


if live:
    render_live()
else:
    fig_hero = hero_figure(yr, tuple(gsel), wvar, secs, mode, pick, show_st2, bool(os.environ.get("NO_TILES")))
    avg = per_year.mean()
    _v = per_year.reindex(range(yr[0], yr[1] + 1), fill_value=0).values
    _pts = " ".join(f"{4 + i * 112 / max(1, len(_v) - 1):.0f},{26 - 22 * v / max(1, _v.max()):.0f}" for i, v in enumerate(_v))
    with st.container(key="hero"):
        st.plotly_chart(fig_hero, width="stretch", config={"displayModeBar": False, "scrollZoom": True}, key="hero_map")
        st.markdown(f"""<div class="hero-ov">
    <div class="tag">NASA SATELLITE DATA · {yr[0]}–{yr[1]}</div>
    <div class="h1">Lebanon Is<br><span class="hot">Burning</span></div>
    <p class="sub">{len(d):,} wildfires detected from space. Where they strike, when, and what they cost our forests.</p>
    <div class="kgrid">
     <div class="kc"><div class="l">Fires detected</div><div class="v">{len(d):,}</div><svg width="120" height="28"><polyline points="{_pts}" fill="none" stroke="#FF6A2B" stroke-width="2"/></svg></div>
     <div class="kc"><div class="l">Worst year</div><div class="v">{per_year.idxmax()}</div><div class="s">{per_year.max():,} fires · about {per_year.max() / avg:.0f}× the average</div></div>
     <div class="kc"><div class="l">Most-burned district</div><div class="v">{by_dist.index[0]}</div><div class="s">{by_dist.iloc[0]:,} fires</div></div>
     <div class="kc"><div class="l">Forest lost to fires</div><div class="v">{fl.loss_ha.sum():,.0f} ha</div><div class="s">central estimate</div></div>
    </div>
    <div class="legend">Fire density<div class="bar"></div><div style="display:flex;justify-content:space-between"><span>Few</span><span>Many</span></div></div>
    </div>""", unsafe_allow_html=True)
    if mode.startswith("One"):
        st.caption(f"Every fire detected in {pick} is a yellow dot; the glow shows where they cluster. Circles are the 5 weather stations "
                   "(red = hotter/drier than normal, blue = cooler/wetter). Satellite imagery: Esri.")
    else:
        st.caption("Press Play: the map moves one week at a time. Each fire flares up bright yellow when detected, then cools to orange and fades "
                   "over six weeks, so fires flow rather than jump. The glow = all fires in the last 12 months. Turn on the 5 weather stations "
                   "in ⚙ Map options (red = hotter/drier than normal for the month, blue = cooler/wetter). Satellite imagery: Esri.")

tab_where, tab_when, tab_why, tab_cost, tab_data = st.tabs(["📍 Where", "📅 When", "🌡️ Why", "🌲 The cost", "📄 Data"])

# ---------- WHERE ----------
# ---------- WHERE ----------
with tab_where:
    st.subheader("Akkar, the Chouf and the South burn most")
    dens = by_dist.rename("fires").reset_index()
    LIGHT_TO_DARK = ["#fdeee6", "#f9c9ad", "#f3a07a", "#eb6834", "#c94d1f", "#9a3412", "#6b2109"]  # fewest -> most fires
    a, b = st.columns([1.25, 1], gap="large")
    with a:
        m = px.choropleth_map(dens, geojson=geo, locations="district", featureidkey="properties.district",
                              color="fires", color_continuous_scale=LIGHT_TO_DARK,
                              hover_data={"fires": ":,", "district": False}, hover_name="district",
                              labels={"fires": "Fires"},
                              map_style="white-bg" if os.environ.get("NO_TILES") else "carto-positron",
                              center={"lat": 33.9, "lon": 35.85}, zoom=7.55, opacity=0.95)
        m.update_traces(marker_line_color="white", marker_line_width=1)
        m.update_layout(coloraxis_colorbar=dict(title="Total fires", thickness=12, len=0.7, tickfont=dict(color=INK2)),
                        showlegend=False)
        m = style(m, 600)
        m.update_layout(paper_bgcolor="rgba(0,0,0,0)", margin=dict(l=0, r=0, t=36, b=0), title="Total fires by district")
        st.plotly_chart(m, width="stretch")
        st.caption("Lighter = fewer fires, darker = more fires (all detections matching the filters above). Basemap © OpenStreetMap contributors © CARTO.")
    with b:
        top = by_dist.head(10).iloc[::-1]
        rank = list(by_dist.head(3).index)
        cols = [FIRE if n in rank else "#C8C6BE" for n in top.index]
        bar = go.Figure(go.Bar(x=top.values, y=top.index, orientation="h", marker_color=cols,
                               text=[f"{v:,}" for v in top.values], textposition="outside",
                               textfont=dict(color=[FIRE if n in rank else MUTED for n in top.index], size=13),
                               cliponaxis=False, hovertemplate="%{y}: %{x:,} fires<extra></extra>"))
        bar.update_layout(title="Top 10 districts by fires", bargap=0.3)
        bar.update_xaxes(showgrid=False, showticklabels=False, range=[0, top.max() * 1.15])
        bar.update_yaxes(showgrid=False, tickfont=dict(size=13))
        bar = style(bar, 600)
        bar.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=8, r=8, t=36, b=0))
        st.plotly_chart(bar, width="stretch")


# ---------- WHEN ----------
with tab_when:
    st.subheader(f"Fire season runs June to October and peaks in {['January','February','March','April','May','June','July','August','September','October','November','December'][d.groupby('month').size().idxmax() - 1]}")
    hm = d.pivot_table(index="year", columns="month", values="frp", aggfunc="size").reindex(columns=range(1, 13)).fillna(0)
    h = go.Figure(go.Heatmap(z=hm.values, x=MONTHS, y=hm.index.astype(str), colorscale=["#fdeee6", "#f9c9ad", "#f3a07a", "#eb6834", "#c94d1f", "#9a3412", "#6b2109"], xgap=2, ygap=2,
                             hovertemplate="%{x} %{y}: %{z:,.0f} fires<extra></extra>", colorbar=dict(thickness=10)))
    h.update_layout(title="Fires per month, every year")
    h.update_yaxes(autorange="reversed", showgrid=False, dtick=1)
    st.plotly_chart(style(h, 460), width="stretch")

    yl = per_year.reindex(range(yr[0], yr[1] + 1), fill_value=0)
    ln = go.Figure(go.Scatter(x=yl.index, y=yl.values, mode="lines+markers", line=dict(color=FIRE, width=2),
                              fill="tozeroy", fillcolor="rgba(255,106,43,0.45)",
                              marker=dict(size=8, color=FIRE, line=dict(color=SURFACE, width=2)),
                              hovertemplate="%{x}: %{y:,} fires<extra></extra>"))
    ln.update_layout(title="Fires per year", hovermode="x")
    ln.update_yaxes(rangemode="tozero")
    st.plotly_chart(style(ln, 300), width="stretch")

# ---------- WHY ----------
with tab_why:
    st.subheader("Hot, dry months bring fire")
    st.caption("Daily weather from five reference sites is aggregated first by site and month, then averaged equally across the five sites. "
               "Monthly rainfall is the mean of each site's monthly precipitation total; temperature, humidity and wind are means of the "
               "site-month daily values. These are reference-site conditions, not weather measured at fire coordinates.")
    WVARS = {"Temperature (°C)": ("temp_max_c", "mean"), "Humidity (%)": ("humidity_mean_pct", "mean"),
             "Rainfall (mm/month)": ("precip_mm", "sum"), "Wind speed (km/h)": ("wind_max_kmh", "mean")}
    wsel = st.selectbox("Explore weather variable", list(WVARS), index=0, key="why_var")
    wcol, wagg = WVARS[wsel]
    w = weather[weather.date.dt.year.between(*yr)].assign(year=lambda x: x.date.dt.year, month=lambda x: x.date.dt.month)
    site_m = w.groupby(["site", "year", "month"])[wcol].agg(wagg).rename("val").reset_index()   # by site and month first
    wm = site_m.groupby(["year", "month"]).val.mean().reset_index()                              # then equal average of sites
    fm = d.groupby(["year", "month"]).size().rename("fires").reset_index()
    j = wm.merge(fm, on=["year", "month"], how="left").fillna({"fires": 0})
    r = j.val.corr(j.fires)
    a, b = st.columns(2, gap="large")
    with a:
        sc = go.Figure(go.Scatter(x=j.val, y=j.fires, mode="markers",
                                  marker=dict(size=11, color=FIRE, opacity=0.75),
                                  customdata=np.c_[j.year, j.month],
                                  hovertemplate="%{customdata[1]}/%{customdata[0]}: %{x:.1f} · %{y:,} fires<extra></extra>"))
        sc.update_layout(title=f"{wsel} versus fire detections", showlegend=False)
        sc.update_xaxes(title=wsel, showgrid=False)
        sc.update_yaxes(title="Fire detections", rangemode="tozero")
        st.plotly_chart(style(sc, 520), width="stretch")
        st.caption(f"Each dot is one month ({yr[0]}–{yr[1]}). Correlation r = {r:.2f}. Correlation is not causation: most fires are started by people.")
    with b:
        n_years = max(1, yr[1] - yr[0] + 1)
        avg_f = (d.groupby("month").size().reindex(range(1, 13), fill_value=0) / n_years)
        avg_w = wm.groupby("month").val.mean().reindex(range(1, 13))
        sp = go.Figure()
        sp.add_bar(x=list(range(1, 13)), y=avg_f.values, name="Avg monthly detections", marker_color=FIRE,
                   hovertemplate="Month %{x}: %{y:.1f} fires on average<extra></extra>")
        sp.add_scatter(x=list(range(1, 13)), y=avg_w.values, name=wsel, yaxis="y2", mode="lines+markers",
                       line=dict(color="#2E8B62", width=3), marker=dict(size=8, color="#2E8B62"),
                       hovertemplate="Month %{x}: %{y:.1f}<extra>" + wsel + "</extra>")
        sp.update_layout(title="Typical seasonal pattern",
                         yaxis=dict(title="Avg detections", rangemode="tozero"),
                         yaxis2=dict(title=wsel, overlaying="y", side="right", showgrid=False,
                                     tickfont=dict(color=MUTED), title_font=dict(color=INK2)),
                         xaxis=dict(title="Month", tickmode="array", tickvals=list(range(1, 13))), bargap=0.2)
        sp = style(sp, 520)
        sp.update_layout(legend=dict(orientation="v", yanchor="top", y=-0.18, x=0.1), margin=dict(l=8, r=8, t=36, b=8))
        st.plotly_chart(sp, width="stretch")

# ---------- COST ----------
with tab_cost:
    nat = loss_nat.copy()
    sel = nat.year.between(*yr)
    tot = nat.loss_ha[sel].sum()
    pk = nat[sel].loc[nat[sel].loss_ha.idxmax()] if sel.any() else nat.loc[nat.loss_ha.idxmax()]
    st.subheader(f"{tot:,.0f} ha of forest lost to fire in {yr[0]}–{yr[1]}, worst in {int(pk.year)}")
    st.caption("Forest loss attributed to fire: Hansen et al. (2013) global 30 m forest-loss data, 2001–2019, extended to 2025 and split "
               "into fire and other drivers. Pixels are coded 4 = high certainty of fire, 3 = medium, 2 = low, 1 = non-fire. "
               "Lower estimate = code 4; central estimate = codes 4 + 3; upper estimate = codes 4 + 3 + 2. "
               "The central estimate is used for all national, governorate and district figures below.")
    est = loss_est.iloc[0]
    k1, k2, k3 = st.columns(3)
    k1.metric("Lower estimate, 2001–2025", f"{est.Lower_ha:,.0f} ha")
    k2.metric("Central estimate, 2001–2025", f"{est.Central_ha:,.0f} ha")
    k3.metric("Upper estimate, 2001–2025", f"{est.Upper_ha:,.0f} ha")

    GREEN, GREEN_LT = "#2E7D5B", "#C9D9CF"
    nb = go.Figure()
    nb.add_bar(x=nat.year[sel], y=nat.loss_ha[sel], name="Selected years", marker_color=GREEN,
               hovertemplate="%{x}: %{y:,.0f} ha<extra></extra>")
    nb.add_bar(x=nat.year[~sel], y=nat.loss_ha[~sel], name="Other years", marker_color=GREEN_LT,
               hovertemplate="%{x}: %{y:,.0f} ha<extra></extra>")
    nb.update_layout(title="National annual forest loss, 2001–2025", bargap=0.2, barmode="overlay",
                     legend=dict(title_text="Selection", orientation="v", x=1.01, y=1, yanchor="top"))
    nb.update_xaxes(dtick=2, title="Year")
    nb.update_yaxes(title="Forest loss (ha)")
    nb = style(nb, 420)
    nb.update_layout(legend=dict(title_text="Selection", orientation="v", x=1.01, y=1, yanchor="top"))
    st.plotly_chart(nb, width="stretch")

    dl = loss_dist[loss_dist.year.between(*yr) & loss_dist.governorate.isin(gsel or loss_dist.governorate.unique())]
    byd = dl.groupby("district").loss_ha.sum().sort_values(ascending=False)
    GREENS = ["#eef6f0", "#cfe6d6", "#a3d0b0", "#6fb487", "#3f945f", "#2E7D5B", "#14532d"]
    c1, c2 = st.columns([1.25, 1], gap="large")
    with c1:
        dm = px.choropleth_map(byd.rename("loss_ha").reset_index(), geojson=geo, locations="district",
                               featureidkey="properties.district", color="loss_ha", color_continuous_scale=GREENS,
                               map_style="white-bg" if os.environ.get("NO_TILES") else "carto-positron",
                               center={"lat": 33.9, "lon": 35.85}, zoom=7.55, opacity=0.95,
                               labels={"loss_ha": "Forest loss (ha)"})
        dm.update_traces(marker_line_color="#ffffff", marker_line_width=0.8,
                         hovertemplate="%{location}: %{z:,.1f} ha<extra></extra>")
        dm.update_layout(title="Forest loss by district · selected years", height=600, margin=dict(l=0, r=0, t=36, b=0),
                         paper_bgcolor="rgba(0,0,0,0)", font_color=INK,
                         coloraxis_colorbar=dict(title="ha", thickness=10, len=0.6))
        st.plotly_chart(dm, width="stretch")
    with c2:
        top = byd.head(10)[::-1]
        first3 = set(byd.index[:3])
        hb = go.Figure(go.Bar(x=top.values, y=top.index, orientation="h",
                              marker_color=[GREEN if n in first3 else "#C8C6BE" for n in top.index],
                              text=[f"{v:,.0f} ha" for v in top.values], textposition="outside",
                              textfont=dict(color=["#6FCF97" if n in first3 else MUTED for n in top.index], size=13), cliponaxis=False,
                              hovertemplate="%{y}: %{x:,.1f} ha<extra></extra>"))
        hb.update_layout(title="Top 10 districts by forest loss", bargap=0.3)
        hb.update_xaxes(showgrid=False, showticklabels=False, range=[0, (top.max() if len(top) else 1) * 1.2])
        hb.update_yaxes(showgrid=False, tickfont=dict(size=13))
        hb = style(hb, 600)
        hb.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=8, r=8, t=36, b=0))
        st.plotly_chart(hb, width="stretch")
    st.caption("District totals exclude about 18 ha of loss in subdivisions flagged as conflict areas, so they sum slightly below the national figure.")

# ---------- DATA ----------
with tab_data:
    st.subheader("All data used in this app")
    DATASETS = {
        "Fire detections (NASA FIRMS VIIRS)": ("lebanon_fires", "Active-fire detections, 2012–2025, matched to governorate, district and cadastral area."),
        "Daily weather (Open-Meteo, 5 sites)": ("lebanon_weather_daily", "Daily temperature, rainfall, humidity, wind and evapotranspiration at five reference sites."),
        "National forest loss to fire, by year": ("forest_loss_national", "Central estimate (codes 4 + 3), hectares per year, 2001–2025."),
        "Forest loss to fire, by district and year": ("forest_loss_districts", "Central estimate aggregated from subdivisions to districts; conflict-area rows excluded."),
        "Forest loss estimates (lower / central / upper)": ("forest_loss_estimates", "National totals 2001–2025 for the three certainty levels."),
        "Fire stations (Civil Defence)": ("fire_stations", "Locations of fire stations used in the hero map overlay."),
    }
    f1, f2 = st.columns([2, 1])
    ds = f1.selectbox("Dataset", list(DATASETS), key="data_ds")
    use_f = f2.toggle("Apply the year and governorate filters", value=True, key="data_f")
    fname, desc = DATASETS[ds]
    gl = gsel or govs

    def get_df(name, filt):
        if name == "lebanon_fires":
            x = d if filt else fires
            return x[["acq_date", "acq_time", "daynight", "governorate", "district", "cadastral_area",
                      "latitude", "longitude", "frp", "confidence", "bright_ti4", "sensor"]]
        if name == "lebanon_weather_daily":
            return weather[weather.date.dt.year.between(*yr)] if filt else weather
        if name == "forest_loss_national":
            return loss_nat[loss_nat.year.between(*yr)] if filt else loss_nat
        if name == "forest_loss_districts":
            return loss_dist[loss_dist.year.between(*yr) & loss_dist.governorate.isin(gl)] if filt else loss_dist
        if name == "forest_loss_estimates":
            return loss_est
        if name == "fire_stations":
            return stations

    view = get_df(fname, use_f)
    st.caption(f"{desc}  ·  {len(view):,} rows")
    if fname in ("forest_loss_estimates", "fire_stations") and use_f:
        st.caption("This dataset has no year field, so the filters don't change it.")
    st.dataframe(view, width="stretch", hide_index=True, height=420)

    b1, b2 = st.columns(2)
    sfx = f"_{yr[0]}_{yr[1]}" if use_f and fname not in ("forest_loss_estimates", "fire_stations") else ""
    b1.download_button(f"⬇ Export this dataset (CSV)", view.to_csv(index=False).encode("utf-8"),
                       f"{fname}{sfx}.csv", "text/csv", width="stretch", key="dl_one")

    import io, zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for _, (n, _) in DATASETS.items():
            z.writestr(f"{n}{'_filtered' if use_f else ''}.csv", get_df(n, use_f).to_csv(index=False))
    b2.download_button("⬇ Export all datasets (ZIP of CSVs)", buf.getvalue(),
                       f"lebanon_wildfires_data{'_filtered' if use_f else ''}.zip", "application/zip",
                       width="stretch", key="dl_all")

st.divider()
st.caption("Sources: NASA FIRMS (VIIRS S-NPP), HDX/CDR administrative boundaries, Open-Meteo, Hansen et al. (2013) forest loss extended to 2025. "
           "MSBA 325 · American University of Beirut · Fall 2026")
