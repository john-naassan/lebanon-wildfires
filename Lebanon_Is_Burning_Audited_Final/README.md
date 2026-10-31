# Lebanon Is Burning — audited Streamlit dashboard

## Run
Place `app.py`, `requirements.txt`, and the **Final data used** directory at the repository root.

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Validation
```bash
python validate.py
```

## Audited corrections
- Monthly heatmap month-axis tick positions corrected to 1–12; October 2024 = 497, November 2024 = 50.
- Fifteen fire records lacking district codes are matched using the supplied governorate + district names. Original code preserved in `district_pcode_original`; all 7,811 observations survive district-year comparisons.
- District choropleth titles adapt to the selected metric.
- Governorate forest-loss heatmap y-axis corrected.
- Forest-loss KPI methodology and source caption match conditional national/selected-area behavior.
- District-year forest-loss joins enforce unique keys and geographic matching is checked.

## Known data/source limitations
- National fire-attributed forest-loss total 2001–2025: 3,180.625 ha; district/governorate/subdivision totals: 3,180.375 ha. Original source discrepancy 0.25 ha is not adjusted.
- VIIRS thermal detections are not unique wildfires or confirmed burned areas.
- Forest loss is mapped fire-attributed loss (central estimate), not total area burned.
- The optional South conflict-period flag describes a period and does not establish ignition cause.
- Weather observations are from five reference sites, not at fire coordinates.
- The density color scale is an exploratory relative intensity, not comparable as a physical unit across filter selections.

## Testing status
`python -m py_compile app.py` and `python validate.py` passed. Full Streamlit browser rendering was not tested in the audit environment because Streamlit was not installed there. Test in the deployment environment before final presentation.
