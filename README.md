# AirLens v2 - Apple-Inspired Air Quality Dashboard

**Wales Air Quality Analysis · Team 16 · Sprint 1**

A beautiful, production-ready dashboard with Apple-inspired design featuring sage green accents, dark mode, and rounded cards.

## 🎨 Design Features

### Visual Identity
- **Dark Mode**: Pure black (#000000) background with layered grays
- **Sage Green Accents**: #8FB569 primary, #A8C686 highlights
- **Rounded Everything**: 18-22px border radius on cards
- **Apple Typography**: Inter font family (SF Pro fallback)
- **Circular Gauges**: Like the reference designs
- **Gradient Text**: For large metric numbers

### Components
- **4 KPI Tiles**: Mean NO₂, Mean PM₂.₅, Exceedance, Completeness
- **Time Series Chart**: Dark Plotly theme with threshold lines
- **Summary Statistics**: 3×2 grid with rounded cells
- **Data Completeness**: Overall % + per-station bars
- **Station Cards**: Dual circular gauges per station

## 📁 Project Structure

```
airlens_v2/
├── app.py                          # Main application
├── requirements.txt                # Dependencies
├── wales_air_quality_data_16.csv  # Your data file (add this)
│
├── assets/
│   └── style.css                  # Apple-inspired CSS (900+ lines)
│
├── components/
│   ├── sidebar.py                 # Filters + WHO/UK toggle
│   ├── kpi_tiles.py              # 4 metric cards
│   └── station_cards.py          # Station detail cards
│
└── utils/
    └── calculations.py            # Rosie + Charles logic combined
```

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Add Your Data
Place `wales_air_quality_data_16.csv` in the project root.

### 3. Run
```bash
python app.py
```

Open **http://127.0.0.1:8052**

## 🔧 Integrated Features

### From Mayowa (Data Loading & Filters)
✅ Site multi-select dropdown
✅ Pollutant dropdown
✅ Date range picker
✅ Dynamic filter updates
✅ Reset button

### From Rosie (Exceedance Logic)
✅ **PM2.5**: Annual mean (UK) or daily exceedances (WHO)
✅ **PM10**: Days exceeding 50 μg/m³ (UK) or 45 (WHO)
✅ **NO2**: Hours exceeding 200 μg/m³ (UK) or daily (WHO)
✅ **SO2**: Days exceeding 125 μg/m³ (UK) or 40 (WHO)
✅ **O3**: 8-hour rolling mean exceedances

### From Charles (Completeness & UI)
✅ Per-site completeness calculation
✅ Overall completeness percentage
✅ Color-coded status (green ≥85%, amber 75-84%, red <75%)
✅ Circular gauge visualizations
✅ KPI tiles with status indicators

### New Features
✅ **WHO/UK Toggle Switch**: Apple-style segmented control
✅ **Sage Green Theme**: Professional environmental aesthetic
✅ **Responsive Grid Layouts**: Auto-adapting card grids
✅ **Dark Mode Throughout**: Consistent #000 / #1C1C1E backgrounds
✅ **Gradient Text**: Large numbers with sage green gradients

## 🎯 Sprint 1 Task Coverage

| Task | Owner | Component | Status |
|------|-------|-----------|--------|
| 1-2 | Mayowa | Data loading | ✅ |
| 3-6 | Mayowa | Filters & chart | ✅ |
| 7-8 | Peris | Summary stats | ✅ |
| 9-10 | Rosie | Exceedance logic | ✅ |
| 11-12 | Charles | Completeness | ✅ |
| 13 | **Gbenga** | **UI Layout** | **✅** |

## 🎨 Color Palette

### Backgrounds
- **Primary**: #000000 (pure black)
- **Secondary**: #1C1C1E (cards)
- **Tertiary**: #2C2C2E (elevated elements)
- **Elevated**: #3A3A3C (hover states)

### Sage Green Accents
- **sage-300**: #A8C686
- **sage-400**: #8FB569
- **sage-500**: #739654
- **sage-600**: #5A7741

### Status Colors
- **Good**: #10B981 (green)
- **Warning**: #F59E0B (amber)
- **Danger**: #EF4444 (red)
- **Purple**: #A855F7 (secondary metrics)

## 📊 Thresholds

### UK Legal Limits
- **NO₂**: 200 μg/m³ (hourly), max 18 exceedances/year
- **PM₁₀**: 50 μg/m³ (daily), max 35 exceedances/year
- **PM₂.₅**: 20 μg/m³ (annual mean)
- **SO₂**: 125 μg/m³ (daily), max 3 exceedances/year
- **O₃**: 120 μg/m³ (8-hour mean), max 10 exceedances/year

### WHO Advisory Guidelines
- **NO₂**: 25 μg/m³ (daily)
- **PM₁₀**: 45 μg/m³ (daily)
- **PM₂.₅**: 15 μg/m³ (daily)
- **SO₂**: 40 μg/m³ (daily)
- **O₃**: 100 μg/m³ (8-hour mean)

## 🔄 How It Works

### Sidebar Toggle (WHO/UK)
```python
# Click toggle button → updates threshold-store
# All callbacks read from threshold-store
# Exceedance calculations use selected standard
```

### KPI Tiles
```python
# Each tile updates based on:
# - Filtered data
# - Selected pollutant
# - Threshold type (WHO/UK)
# - Status class changes color (good/warning/danger)
```

### Station Cards
```python
# For each selected station:
# - Calculate exceedance (left gauge)
# - Calculate completeness (right gauge)
# - Color-code rings based on status
```

## 🐛 Troubleshooting

**Issue**: "ModuleNotFoundError: No module named 'dash'"  
**Fix**: `pip install -r requirements.txt`

**Issue**: Dropdowns are empty  
**Fix**: Check CSV has columns: `date`, `site`, `NO2`, `PM2.5`, `PM10`, `O3`, `SO2`

**Issue**: CSS not loading  
**Fix**: Ensure `assets/style.css` exists in same folder as `app.py`

**Issue**: Toggle not working  
**Fix**: Make sure `dash-daq` is installed: `pip install dash-daq`

## 💡 Customization

### Change Accent Color
Edit `/assets/style.css` line 18-24:
```css
--sage-400: #8fb569;  /* Change to your color */
```

### Adjust Card Radius
Edit `/assets/style.css` line 44-48:
```css
--radius-lg: 18px;  /* Make more/less rounded */
--radius-xl: 22px;
```

### Modify Thresholds
Edit `/utils/calculations.py` lines 15-31:
```python
LIMITS = {
    'UK': {
        'NO2': {'hourly': 200, ...},
        # Modify values here
    }
}
```

## 📚 Key Files Explained

### `app.py`
Main application with all callbacks. Combines Mayowa's filters, Rosie's exceedance logic, and Charles' completeness calculations.

### `assets/style.css`
900+ lines of Apple-inspired CSS. Dark mode, sage green accents, responsive grids.

### `utils/calculations.py`
All calculation logic:
- `calculate_exceedance_rosie()` - Rosie's sophisticated logic
- `calculate_completeness()` - Charles' completeness calc
- `calculate_summary_stats()` - Mean, median, std, etc.

### `components/sidebar.py`
Sidebar with:
- WHO/UK toggle switch
- Site multi-select
- Pollutant dropdown
- Date range picker
- Reset button

## 🎓 Next Steps (Sprint 2)

Potential enhancements:
- [ ] Rosie's bar chart visualization
- [ ] Export data/charts
- [ ] Map view of stations
- [ ] Statistical modeling panel
- [ ] Year-over-year comparison

## 👥 Credits

**Team 16**
- Mayowa: Data loading, filters, time-series chart
- Peris: Summary statistics
- Rosie: Exceedance logic
- Charles (Thway): Completeness calculations
- **Gbenga**: UI/UX layout & design

---

**Built with ❤️ for environmental research**  
DEFRA AURN Data · Wales Air Quality Monitoring
