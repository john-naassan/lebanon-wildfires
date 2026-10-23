"""Lebanon Is Burning - MSBA 325 wildfire dashboard (Streamlit + Plotly)."""
import base64
import json
import os
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
INK, INK2, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, AXIS, SURFACE = "#e1e0d9", "#c3c2b7", "#fcfcfb"
FIRE, OTHER = "#eb6834", "#2a78d6"            # categorical slots 2 and 1
FIRE_RAMP = ["#fdeee6", "#f9c9ad", "#f3a07a", "#eb6834", "#c94d1f", "#9a3412", "#6b2109"]  # one hue, light->dark
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
FONT = "system-ui, -apple-system, Segoe UI, sans-serif"


def style(fig, h=380):
    fig.update_layout(
        height=h, margin=dict(l=8, r=8, t=36, b=8), paper_bgcolor=SURFACE, plot_bgcolor=SURFACE,
        font=dict(family=FONT, color=INK2, size=13), title_font=dict(color=INK, size=15),
        hoverlabel=dict(bgcolor="white", font_color=INK, bordercolor=AXIS), legend=dict(orientation="h", yanchor="top", y=-0.12, x=0),
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

# ---------- header ----------
st.title("🔥 Lebanon Is Burning")
st.markdown("**Where and when wildfires strike, and what they cost our forests (2012–2025).** "
            "Satellite fire detections from NASA, matched to every district in Lebanon.")

# ---------- filters (one row) ----------
c1, c2 = st.columns([1, 1])
yr = c1.slider("Years", 2012, 2025, (2012, 2025))
govs = sorted(g for g in fires.governorate.dropna().unique() if g != "Beirut")
gsel = c2.multiselect("Governorates", govs, default=[], placeholder="All governorates")

d = fires[fires.year.between(*yr) & fires.governorate.isin(gsel or govs) & ~fires.urban_industrial]
if d.empty:
    st.warning("No fires match these filters.")
    st.stop()

# ---------- KPI tiles ----------
per_year = d.groupby("year").size()
by_dist = d.groupby("district").size().sort_values(ascending=False)
peak_m = d.groupby("month").size().idxmax()
fl = loss[loss.year.between(*yr)]
k1, k2, k3, k4 = st.columns(4)
k1.metric("Fires detected", f"{len(d):,}", help="NASA VIIRS detections, vegetation fires, nominal/high confidence")
k2.metric("Worst year", f"{per_year.idxmax()}")
k2.caption(f"{per_year.max():,} fires")
k3.metric("Most-burned district", by_dist.index[0])
k3.caption(f"{by_dist.iloc[0]:,} fires")
k4.metric("Forest lost to fires", f"{fl.loss_from_fires_ha.sum():,.0f} ha")
k4.caption(f"{100 * fl.loss_from_fires_ha.sum() / fl.tree_cover_loss_ha.sum():.0f}% of all tree cover lost in these years (national)")

tab1, tab0, tab2, tab3, tab4, tab5 = st.tabs(["📍 Where", "▶️ Year by year", "📅 When", "🌡️ Why", "🌲 The cost", "📄 Data"])

# ---------- WHERE ----------
with tab1:
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
            base_layers = [dict(source=geo_border, type="line", color="#555555", line=dict(width=1.5), below="traces")]
            m.update_layout(map=dict(style="white-bg" if os.environ.get("NO_TILES") else "carto-voyager",
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
                                  map_style="white-bg", center={"lat": 33.88, "lon": 35.85}, zoom=6.9, opacity=0.9)
            m.update_traces(marker_line_color="white", marker_line_width=1)
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


# ---------- YEAR BY YEAR (animated satellite map) ----------
with tab0:
    st.subheader("Watch fires and weather move through time")
    c1, c2, c3 = st.columns([1.3, 1.1, 1])
    mode = c1.radio("Show", ["Animation, month by month", "One whole year"], horizontal=True, key="yy_mode")
    wvar = c2.radio("Weather at the stations", ["Temperature vs normal", "Rainfall vs normal"], horizontal=True, key="yy_w")
    years = list(range(yr[0], yr[1] + 1))
    if mode.startswith("One"):
        pick = c3.selectbox("Year", years[::-1], key="yy_year")
    else:
        secs = c3.slider("Seconds per year", 7, 10, 8, key="yy_secs",
                         help="How long each year takes to play. Each month is one step.")
    show_st2 = st.toggle("Show fire stations", value=True, key="st_sat")
    is_temp = wvar.startswith("Temp")
    MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    HEAT = [[0, "rgba(0,0,255,0)"], [0.08, "rgba(40,60,255,0.35)"], [0.25, "rgba(0,200,255,0.55)"],
            [0.45, "rgba(0,210,90,0.65)"], [0.65, "rgba(255,230,0,0.75)"], [0.82, "rgba(255,140,0,0.85)"],
            [1, "rgba(230,20,20,0.95)"]]
    # diverging: blue (cooler / wetter) <-> grey <-> red (hotter / drier)
    DIV = [[0, "#1c5cab"], [0.25, "#6da7ec"], [0.5, "#d9d8d2"], [0.75, "#ec835a"], [1, "#d03b3b"]]
    if not is_temp:
        DIV = [[0, DIV[4][1]], [0.25, DIV[3][1]], [0.5, DIV[2][1]], [0.75, DIV[1][1]], [1, DIV[0][1]]]
    LABEL_POS = {"Akkar": "middle right", "Batroun": "middle left", "Metn": "top left",
                 "Chouf": "bottom left", "Zahle (Bekaa)": "middle right"}

    def station_traces(sy, acol, lim, unit):
        """White ring + station circle coloured by weather vs normal + one label per station."""
        ring = go.Scattermap(lat=sy.lat, lon=sy.lon, mode="markers", marker=dict(size=26, color="white"), hoverinfo="skip")
        stn = go.Scattermap(lat=sy.lat, lon=sy.lon, mode="markers",
                            marker=dict(size=21, color=sy[acol], colorscale=DIV, cmin=-lim, cmax=lim, showscale=False),
                            customdata=sy[["site", "temp", "rain", "temp_anom", "rain_anom"]],
                            hovertemplate="<b>%{customdata[0]}</b><br>Avg max temp %{customdata[1]:.1f}°C "
                                          "(%{customdata[3]:+.1f}°C vs normal)<br>Rain %{customdata[2]:.0f} mm "
                                          "(%{customdata[4]:+.0f} " + unit + " vs normal)<extra></extra>")
        labels = []
        for site, pos in LABEL_POS.items():
            r = sy[sy.site == site]
            name = site.replace(" (Bekaa)", "")
            txt = [f"{name} {v:+.1f}°C" if is_temp else f"{name} {v:+.0f} {unit} rain" for v in r[acol]]
            txt = [f"   {t}" if "right" in pos else f"{t}   " for t in txt]
            labels.append(go.Scattermap(lat=r.lat, lon=r.lon, mode="markers+text", textposition=pos, text=txt,
                                        marker=dict(size=26, color="rgba(0,0,0,0)"), hoverinfo="skip",
                                        textfont=dict(color="white", size=13)))
        return [ring, stn, *labels]

    def fire_dots(fx, size, color, opacity, hover=True):
        return go.Scattermap(lat=fx.latitude, lon=fx.longitude, mode="markers",
                             marker=dict(size=size, color=color, opacity=opacity),
                             customdata=fx[["district", "acq_date"]].astype(str) if hover else None,
                             hovertemplate="Fire in %{customdata[0]}<br>%{customdata[1]}<extra></extra>" if hover else None,
                             hoverinfo=None if hover else "skip")

    if mode.startswith("One"):
        # ---- one whole year: every fire of that year + weather for the whole year ----
        fy = d[d.year == pick]
        wy = (weather.assign(year=weather.date.dt.year).groupby(["year", "site"])
              .agg(temp=("temp_max_c", "mean"), rain=("precip_mm", "sum"),
                   lat=("latitude", "first"), lon=("longitude", "first")).reset_index())
        wy["temp_anom"] = wy.temp - wy.groupby("site").temp.transform("mean")
        wy["rain_anom"] = 100 * (wy.rain / wy.groupby("site").rain.transform("mean") - 1)
        acol = "temp_anom" if is_temp else "rain_anom"
        lim = float(wy[acol].abs().max())
        sy = wy[wy.year == pick]
        zmax = max(3.0, 0.006 * len(fy))
        traces = [go.Densitymap(lat=fy.latitude, lon=fy.longitude, radius=16, colorscale=HEAT, zmin=0, zmax=zmax,
                                zauto=False, showscale=False, hoverinfo="skip"),
                  fire_dots(fy, 5, "#ffe066", 0.9)] + station_traces(sy, acol, lim, "%")
        t_mean, r_mean = sy.temp_anom.mean(), sy.rain_anom.mean()
        title = (f"<b>{pick}</b> · {len(fy):,} fires · {'hotter' if t_mean > 0 else 'cooler'} than normal "
                 f"({t_mean:+.1f}°C) · rain {r_mean:+.0f}% vs normal")
        frames, menus, sliders = [], [], []
    else:
        # ---- animation: one frame per month; the heat map is a rolling 12 months so it flows, never resets ----
        wm = (weather.assign(year=weather.date.dt.year, month=weather.date.dt.month)
              .groupby(["year", "month", "site"])
              .agg(temp=("temp_max_c", "mean"), rain=("precip_mm", "sum"),
                   lat=("latitude", "first"), lon=("longitude", "first")).reset_index())
        wm["temp_anom"] = wm.temp - wm.groupby(["site", "month"]).temp.transform("mean")
        wm["rain_anom"] = wm.rain - wm.groupby(["site", "month"]).rain.transform("mean")
        acol = "temp_anom" if is_temp else "rain_anom"
        lim = float(wm[acol].abs().quantile(0.98))
        dm = d.assign(t=d.year * 12 + d.month - 1)
        steps_t = [y * 12 + m for y in years for m in range(12)]
        avg12 = max(1, len(dm) / max(1, len(years)))
        zmax = max(3.0, 0.008 * avg12)
        cnt = dm.groupby("t").size()

        def frame_data(t):
            y, m = divmod(t, 12)
            last12 = dm[(dm.t > t - 12) & (dm.t <= t)]
            now, prev1, prev2 = dm[dm.t == t], dm[dm.t == t - 1], dm[dm.t == t - 2]
            sy = wm[(wm.year == y) & (wm.month == m + 1)]
            tr = [go.Densitymap(lat=last12.latitude, lon=last12.longitude, radius=16, colorscale=HEAT,
                                zmin=0, zmax=zmax, zauto=False, showscale=False, hoverinfo="skip"),
                  fire_dots(prev2, 4, "#ff8c1a", 0.35, hover=False),
                  fire_dots(prev1, 5, "#ffb000", 0.6, hover=False),
                  fire_dots(now, 8, "#fff3a0", 1.0)] + station_traces(sy, acol, lim, "mm")
            tm = sy.temp_anom.mean()
            ttl = (f"<b>{MONTH_NAMES[m]} {y}</b> · {int(cnt.get(t, 0)):,} fires this month · "
                   f"{int(last12.shape[0]):,} in the last 12 months · "
                   f"{'hotter' if tm > 0 else 'cooler'} than a normal {MONTH_NAMES[m]} ({tm:+.1f}°C)")
            return tr, ttl

        traces, title = frame_data(steps_t[0])
        frames = []
        for t in steps_t:
            tr, ttl = frame_data(t)
            frames.append(go.Frame(data=tr, name=str(t), layout=go.Layout(title_text=ttl)))
        ms = int(secs * 1000 / 12)
        menus = [dict(type="buttons", direction="left", x=1, y=1.0, xanchor="right", yanchor="bottom",
                      pad=dict(r=8, t=8), showactive=False,
                      buttons=[dict(label="▶ Play", method="animate",
                                    args=[None, dict(frame=dict(duration=ms, redraw=True),
                                                     transition=dict(duration=0), fromcurrent=True)]),
                               dict(label="❚❚ Pause", method="animate",
                                    args=[[None], dict(frame=dict(duration=0, redraw=False),
                                                       mode="immediate", transition=dict(duration=0))])])]
        sliders = [dict(active=0, x=0, len=1, y=-0.02, yanchor="top", pad=dict(t=10),
                        currentvalue=dict(visible=False), ticklen=3, minorticklen=0,
                        steps=[dict(label=str(t // 12) if t % 12 == 0 else "", method="animate",
                                    args=[[str(t)], dict(mode="immediate", frame=dict(duration=0, redraw=True),
                                                         transition=dict(duration=0))]) for t in steps_t])]

    sat = go.Figure(data=traces + ([station_hover()] if show_st2 else []))
    sat.frames = frames
    sat.update_layout(
        title=title, showlegend=False, updatemenus=menus, sliders=sliders,
        map=dict(
            style="white-bg", center={"lat": 33.9, "lon": 35.85}, zoom=7.4,
            layers=([] if os.environ.get("NO_TILES") else [
                # satellite imagery (Esri World Imagery) + place-name labels, like Google satellite view
                dict(sourcetype="raster", below="traces", sourceattribution="Imagery © Esri, Maxar, Earthstar Geographics",
                     source=["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"]),
                dict(sourcetype="raster", below="traces",
                     source=["https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}"])]) + [
                # Lebanon's border, dashed red like Google Maps
                dict(source=geo_border, type="line", color="#ff4d4d", line=dict(width=2.5, dash=[2, 1.5]), below="traces"),
            ] + (station_layers(0.045) if show_st2 else [])))
    st.plotly_chart(style(sat, 720).update_layout(margin=dict(l=8, r=8, t=80, b=90 if frames else 20)), width="stretch")
    if mode.startswith("One"):
        k = "Red = hotter than that station's 2012–2025 average for the year, blue = cooler." if is_temp else \
            "Red = drier than that station's 2012–2025 average for the year, blue = wetter."
        st.caption(f"Every fire detected in {pick} is shown as a yellow dot; the heat glow shows where they cluster. "
                   f"Circles are the 5 weather stations. {k} Satellite imagery: Esri.")
    else:
        k = "Red = hotter than normal for that month, blue = cooler." if is_temp else \
            "Red = drier than normal for that month, blue = wetter (mm difference)."
        st.caption("Press Play: each step is one month. Bright yellow dots = fires this month, fading orange = the two months before; "
                   f"the heat glow = all fires in the last 12 months, so it builds and fades instead of resetting each year. "
                   f"Circles are the 5 weather stations. {k} Satellite imagery: Esri.")


# ---------- WHEN ----------
with tab2:
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
with tab3:
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
with tab4:
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
with tab5:
    st.dataframe(d[["acq_date", "governorate", "district", "cadastral_area", "latitude", "longitude", "frp", "confidence"]],
                 width="stretch", hide_index=True)
    st.download_button("Download filtered fires (CSV)", d.to_csv(index=False), "lebanon_fires_filtered.csv", "text/csv")

st.divider()
st.caption("Sources: NASA FIRMS (VIIRS S-NPP), HDX/CDR administrative boundaries, Open-Meteo, Global Forest Watch. "
           "MSBA 325 · American University of Beirut · Fall 2026")
