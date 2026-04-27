# UK Air Quality Dashboard

Interactive air quality analysis dashboard for Wales, UK. The application transforms complex air quality datasets into clear, usable insights through multi-site filtering, pollutant analysis, threshold exceedance checks, temporal visualisations, and AQI forecasting.

## Overview

This project provides a web-based dashboard for exploring UK air quality data, with a focus on Wales. It is designed for environmental analysts, researchers, policymakers, and users who need to understand pollutant trends, compare monitoring sites, and interpret air quality patterns more easily.

The dashboard supports analysis of key pollutants across multiple monitoring sites, including:

- NO₂
- O₃
- SO₂
- PM10
- PM2.5

## Key Features

- Multi-site and multi-pollutant filtering
- Interactive Dash and Plotly visualisations
- Time-series trend analysis
- Daily, weekly, monthly, and seasonal pollutant views
- UK and WHO threshold comparison
- Exceedance detection
- Summary statistics and data completeness checks
- Correlation heatmaps
- Temperature relationship scatter plots
- Pollution rose charts
- 7-day AQI forecasting using XGBoost
- AI-generated forecast explanations using Gemini
- Light and dark mode interface
- Modular Python Dash code structure

## Tech Stack

- Python
- Dash
- Plotly
- Pandas
- NumPy
- Statsmodels
- Scikit-learn
- XGBoost
- PyArrow / Parquet
- Google Gemini API
- Pytest

## Project Structure

```text
AirQualityDashboard/
├── data/                  # Data files and processed datasets
├── src/
│   ├── app.py             # Main Dash app entry point
│   ├── callbacks.py       # Dashboard callbacks and chart logic
│   ├── dataloader.py      # Data loading utilities
│   ├── layout.py          # Main app layout
│   ├── assets/            # CSS and static assets
│   ├── components/        # Reusable UI components
│   ├── pages/             # Dashboard pages
│   └── utils/             # Calculations, forecasting, weather, and insight utilities
├── test/                  # Unit tests
├── requirements.txt       # Python dependencies
└── README.md
```

## Installation

Clone the repository:

```bash
git clone https://github.com/Kyawsittthway/AirQualityDashboard.git
cd AirQualityDashboard
```

Create and activate a virtual environment:

```bash
python -m venv .venv
```

On macOS/Linux:

```bash
source .venv/bin/activate
```

On Windows:

```bash
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Gemini API Setup

The forecast insight feature uses the Google Gemini API.

1. Go to Google AI Studio.
2. Create a Gemini API key.
3. Add the key as an environment variable.

On macOS/Linux:

```bash
export GEMINI_API_KEY="PASTE_YOUR_GEMINI_API_KEY_HERE"
```

On Windows PowerShell:

```powershell
$env:GEMINI_API_KEY="PASTE_YOUR_GEMINI_API_KEY_HERE"
```

## Running the App

Run the Dash application:

```bash
python src/app.py
```

Then open the local Dash URL shown in the terminal, usually:

```text
http://127.0.0.1:8050/
```

## Testing

Run the test suite with:

```bash
pytest
```

## Dashboard Pages

### Overview

Provides headline KPIs, pollutant trends, summary statistics, data completeness, and temporal analysis.

### Comparison

Allows users to compare sites using temperature relationships, correlation heatmaps, and pollution rose charts.

### Exceedance

Checks pollutant values against UK and WHO standards and highlights exceedance behaviour.

### Forecast

Provides a 7-day AQI forecast using historical pollutant data, weather features, and XGBoost-based prediction, supported by AI-generated explanations.

## Results

The project delivered a working analytical dashboard with:

- Multi-site and multi-pollutant visualisation
- Real-time chart updates through filtering
- Fast response and loading performance
- AQI forecasting with uncertainty interpretation
- Clear, human-readable insights for users

## Future Enhancements

- Predictive AQI alerts
- UK-wide data coverage
- Interactive AQI map
- Containerised deployment
- Mobile-optimised web interface

## Licence and Data Use

This project uses UK air quality data for analytical and educational purposes. Users should ensure correct attribution of public datasets and comply with the relevant Open Government Licence, data source terms, and privacy requirements.

## Acknowledgements

This dashboard was developed as a group project to make air quality data more accessible, interactive, and meaningful for analysis and decision-making.

