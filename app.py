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
    loss = pd.read_csv(P("forest_loss_2001_2025.csv"))
    geo = json.load(open(P("districts.geojson")))
    border = json.load(open(P("lebanon_border.geojson")))
    stations = pd.read_csv(P("fire_stations.csv"))
    icon = "data:image/png;base64," + base64.b64encode(open(P("station_icon.png"), "rb").read()).decode()
    return f, w, loss, geo, border, stations, icon


fires, weather, loss, geo, geo_border, stations, ICON = load()


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
.block-container{padding-top:0 !important;max-width:1440px}
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
.st-key-filters{position:relative;z-index:30;width:min(640px,52vw);margin-left:auto;top:14px;margin-bottom:-74px}
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
</style>""", unsafe_allow_html=True)

# ---------- filters: slim chips floating over the map ----------
govs = sorted(g for g in fires.governorate.dropna().unique() if g != "Beirut")
with st.container(key="filters"):
    c1, c2, c3 = st.columns([1, 1.25, 1])
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

d = fires[fires.year.between(*yr) & fires.governorate.isin(gsel or govs) & ~fires.urban_industrial]
if d.empty:
    st.warning("No fires match these filters.")
    st.stop()

per_year = d.groupby("year").size()
by_dist = d.groupby("district").size().sort_values(ascending=False)
fl = loss[loss.year.between(*yr)]

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
    dd = fires[fires.year.between(*yr) & fires.governorate.isin(list(gsel) or govs) & ~fires.urban_industrial].copy()
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
 <div class="kc"><div class="l">Forest lost to fires</div><div class="v">{fl.loss_from_fires_ha.sum():,.0f} ha</div><div class="s">{100 * fl.loss_from_fires_ha.sum() / fl.tree_cover_loss_ha.sum():.0f}% of tree loss</div></div>
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
    dens = (by_dist.rename("fires").reset_index()
            .assign(per_100km2=lambda x: 100 * x.fires / x.district.map(area)))
    a, b = st.columns([1.25, 1])
    with a:
        view = st.radio("Map view", ["Heat map", "Districts"], horizontal=True, key="where_view")
        if view == "Heat map":
            # hot-spot heat map: transparent where there are no fires, blue -> green -> yellow -> red where they cluster
            HEAT = [[0, "rgba(0,0,255,0)"], [0.08, "rgba(40,60,255,0.35)"], [0.25, "rgba(0,200,255,0.55)"],
                    [0.45, "rgba(0,210,90,0.65)"], [0.65, "rgba(255,230,0,0.75)"], [0.82, "rgba(255,140,0,0.85)"],
                    [1, "rgba(230,20,20,0.95)"]]
            radius = st.slider("Heat spread", 6, 30, 14, key="heat_radius",
                               help="Bigger = smoother, regional picture. Smaller = individual hot spots.")
            # scale the colour range to how many fires are shown and how wide each glow is, so the map never saturates
            zmax = max(3.0, 0.004 * len(d) * (radius / 14) ** 2)
            m = go.Figure(go.Densitymap(lat=d.latitude, lon=d.longitude, radius=radius, colorscale=HEAT,
                                        zmin=0, zmax=zmax, zauto=False, showscale=True, hoverinfo="skip",
                                        colorbar=dict(title="Fire density", thickness=10, len=0.5,
                                                      tickvals=[0, zmax], ticktext=["Few", "Many"])))
            base_layers = [dict(source=geo_border, type="line", color="#9a948b", line=dict(width=1.5), below="traces")]
            m.update_layout(map=dict(style="white-bg" if os.environ.get("NO_TILES") else "carto-darkmatter",
                                     center={"lat": 33.85, "lon": 35.85}, zoom=7.0, layers=base_layers))
        else:
            base_layers = []
            metric = st.radio("Colour districts by", ["Fires per 100 km²", "Total fires"], horizontal=True)
            col = "per_100km2" if metric.startswith("Fires per") else "fires"
            m = px.choropleth_map(dens, geojson=geo, locations="district", featureidkey="properties.district",
                              color=col, color_continuous_scale=FIRE_RAMP,
                                  hover_data={"fires": ":,", "per_100km2": ":.1f", "district": False},
                                  hover_name="district", labels={"per_100km2": "Fires / 100 km²", "fires": "Fires"},
                                  range_color=(0, 250) if col == "per_100km2" else None,
                                  map_style="white-bg" if os.environ.get("NO_TILES") else "carto-darkmatter", center={"lat": 33.88, "lon": 35.85}, zoom=6.9, opacity=0.9)
            m.update_traces(marker_line_color="#0E1013", marker_line_width=1)
            pts = d
            m.add_trace(go.Scattermap(lat=pts.latitude, lon=pts.longitude, mode="markers", name="Fire",
                                      marker=dict(size=4, color=INK, opacity=0.35), hoverinfo="skip"))
        show_st = st.toggle("Show fire stations", value=True, key="st_where",
                            help=f"{len(stations)} fire and Civil Defence stations mapped on OpenStreetMap (October 2026). Hover an emblem for its name.")
        if show_st:
            m.add_trace(station_hover())
            m.update_layout(map_layers=base_layers + list(station_layers(0.05)))
        m.update_layout(coloraxis_colorbar=dict(title="", thickness=10, len=0.6), showlegend=False)
        st.plotly_chart(style(m, 560 if view == "Heat map" else 520), width="stretch")
        if view == "Heat map":
            st.caption("Red and yellow = where satellite fire detections cluster most; blue = few; no colour = none. "
                       "Uses every fire that matches the filters above. Basemap © OpenStreetMap contributors © CARTO.")
        else:
            st.caption("Each dark dot is a satellite fire detection (all fires matching the filters); red badges are fire and Civil Defence stations. Fires per 100 km² stops big districts looking worse just because they are big. "
                       "Tripoli is off the scale: it is a small city district, so many of its detections are likely waste or urban burning rather than forest fires.")
    with b:
        top = by_dist.head(10).iloc[::-1]
        bar = go.Figure(go.Bar(x=top.values, y=top.index, orientation="h", marker_color=FIRE,
                               text=[f"{v:,}" for v in top.values], textposition="outside",
                               textfont_color=INK2, cliponaxis=False, hovertemplate="%{y}: %{x:,} fires<extra></extra>"))
        bar.update_layout(title="Top 10 districts by fires")
        bar.update_xaxes(showgrid=False, showticklabels=False, range=[0, top.max() * 1.18])
        bar.update_yaxes(showgrid=False)
        st.plotly_chart(style(bar, 520), width="stretch")


# ---------- WHEN ----------
with tab_when:
    st.subheader(f"Fire season runs June to October and peaks in {['January','February','March','April','May','June','July','August','September','October','November','December'][d.groupby('month').size().idxmax() - 1]}")
    hm = d.pivot_table(index="year", columns="month", values="frp", aggfunc="size").reindex(columns=range(1, 13)).fillna(0)
    h = go.Figure(go.Heatmap(z=hm.values, x=MONTHS, y=hm.index.astype(str), colorscale=FIRE_RAMP, xgap=2, ygap=2,
                             hovertemplate="%{x} %{y}: %{z:,.0f} fires<extra></extra>", colorbar=dict(thickness=10)))
    h.update_layout(title="Fires per month, every year")
    h.update_yaxes(autorange="reversed", showgrid=False, dtick=1)
    st.plotly_chart(style(h, 460), width="stretch")

    yl = per_year.reindex(range(yr[0], yr[1] + 1), fill_value=0)
    ln = go.Figure(go.Scatter(x=yl.index, y=yl.values, mode="lines+markers", line=dict(color=FIRE, width=2),
                              marker=dict(size=8, color=FIRE, line=dict(color=SURFACE, width=2)),
                              hovertemplate="%{x}: %{y:,} fires<extra></extra>"))
    ln.update_layout(title="Fires per year", hovermode="x")
    ln.update_yaxes(rangemode="tozero")
    st.plotly_chart(style(ln, 300), width="stretch")

# ---------- WHY ----------
with tab_why:
    st.subheader("Hot, dry months bring fire")
    w = weather[weather.date.dt.year.between(*yr)]
    wm = (w.assign(year=w.date.dt.year, month=w.date.dt.month)
          .groupby(["year", "month"]).agg(temp=("temp_max_c", "mean"), rain=("precip_mm", "sum"),
                                         hum=("humidity_mean_pct", "mean")).reset_index())
    wm["rain"] = wm.rain / w.site.nunique()
    fm = d.groupby(["year", "month"]).size().rename("fires").reset_index()
    j = wm.merge(fm, on=["year", "month"], how="left").fillna({"fires": 0})
    a, b = st.columns(2)
    with a:
        sc = px.scatter(j, x="temp", y="fires", hover_data={"year": True, "month": True},
                        labels={"temp": "Average daily max temperature (°C)", "fires": "Fires that month"})
        sc.update_traces(marker=dict(size=9, color=FIRE, opacity=0.75, line=dict(color=SURFACE, width=1.5)))
        sc.update_layout(title=f"Every month 2012–2025: hotter months burn more (r = {j.temp.corr(j.fires):.2f})")
        st.plotly_chart(style(sc, 400), width="stretch")
    with b:
        sc2 = px.scatter(j, x="hum", y="fires", hover_data={"year": True, "month": True},
                         labels={"hum": "Average humidity (%)", "fires": "Fires that month"})
        sc2.update_traces(marker=dict(size=9, color=FIRE, opacity=0.75, line=dict(color=SURFACE, width=1.5)))
        sc2.update_layout(title=f"Drier air, more fires (r = {j.hum.corr(j.fires):.2f})")
        st.plotly_chart(style(sc2, 400), width="stretch")
    st.caption("Weather is the average of 5 sites (Akkar, Batroun, Metn, Chouf, Zahle) from Open-Meteo. Correlation is not causation: most fires are still started by people.")

# ---------- COST ----------
with tab_cost:
    st.subheader("Since 2019, fires eat a much bigger share of our forests")
    fl2 = loss.assign(other=loss.tree_cover_loss_ha - loss.loss_from_fires_ha)
    st_ = go.Figure()
    st_.add_bar(x=fl2.year, y=fl2.other, name="Other causes", marker_color=OTHER,
                hovertemplate="%{x}: %{y:,.0f} ha other causes<extra></extra>")
    st_.add_bar(x=fl2.year, y=fl2.loss_from_fires_ha, name="Lost to fires", marker_color=FIRE,
                customdata=fl2.share_from_fires_pct,
                hovertemplate="%{x}: %{y:,.0f} ha to fires (%{customdata:.0f}%)<extra></extra>")
    st_.update_layout(barmode="stack", bargap=0.25, title="Tree cover lost each year (hectares)")
    st_.update_traces(marker_line_color=SURFACE, marker_line_width=2)
    peak = fl2.loc[fl2.share_from_fires_pct.idxmax()]
    st_.add_annotation(x=peak.year, y=peak.tree_cover_loss_ha, text=f"{int(peak.year)}: {peak.share_from_fires_pct:.0f}% from fires",
                       showarrow=True, arrowcolor=MUTED, ay=-40, font=dict(color=INK, size=12))
    st.plotly_chart(style(st_, 460), width="stretch")
    before = loss[loss.year.between(2001, 2018)]
    after = loss[loss.year.between(2019, 2025)]
    x1, x2 = st.columns(2)
    x1.metric("Share of tree loss from fires, 2001–2018", f"{100 * before.loss_from_fires_ha.sum() / before.tree_cover_loss_ha.sum():.0f}%")
    x2.metric("Share of tree loss from fires, 2019–2025", f"{100 * after.loss_from_fires_ha.sum() / after.tree_cover_loss_ha.sum():.0f}%")
    st.caption("Source: Global Forest Watch (University of Maryland), tree cover with ≥30% canopy.")

# ---------- DATA ----------
with tab_data:
    st.dataframe(d[["acq_date", "governorate", "district", "cadastral_area", "latitude", "longitude", "frp", "confidence"]],
                 width="stretch", hide_index=True)
    st.download_button("Download filtered fires (CSV)", d.to_csv(index=False), "lebanon_fires_filtered.csv", "text/csv")

st.divider()
st.caption("Sources: NASA FIRMS (VIIRS S-NPP), HDX/CDR administrative boundaries, Open-Meteo, Global Forest Watch. "
           "MSBA 325 · American University of Beirut · Fall 2026")
