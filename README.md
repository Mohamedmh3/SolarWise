# SolarWise

SolarWise is a desktop solar-energy advisor for household PV systems. It combines
historical NASA POWER weather data, a machine-learning solar-radiation forecast,
household appliance profiles, and battery simulation to recommend when flexible
loads should run.

The application provides a focused Tkinter dashboard for:

- PV generation and household-demand estimates
- Battery state-of-charge and energy-flow simulation
- Appliance scheduling around forecast solar availability
- Best-time recommendations and daily notifications
- Runtime provenance, including the dataset period and selected model

> **Modeling note:** SolarWise produces modeled estimates for PV generation,
> household demand, and battery flows. It is intended for analysis and planning,
> not as a substitute for certified electrical, safety, or financial advice.

## Requirements

- Python 3.10 or newer
- Tkinter (usually included with standard Python installations)
- Dependencies listed in [`requirements.txt`](requirements.txt)

## Quick start

1. Clone the repository and enter the project directory:

   ```bash
   git clone https://github.com/Mohamedmh3/SolarWise.git
   cd SolarWise
   ```

2. Create and activate a virtual environment:

   **Windows PowerShell**

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   **macOS/Linux**

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. Install dependencies:

   ```bash
   python -m pip install -r requirements.txt
   ```

4. Start the desktop application:

   ```bash
   python ui.py
   ```

   On first run, SolarWise trains the configured model and creates
   `best_model.joblib` locally. This generated artifact is intentionally ignored
   by Git; subsequent runs reuse it.

## Project structure

| File | Purpose |
| --- | --- |
| [`ui.py`](ui.py) | Tkinter desktop interface and user interactions |
| [`analysis.py`](analysis.py) | Runtime adapter connecting the UI to analysis |
| [`pipeline.py`](pipeline.py) | Feature engineering, model training, PV estimation, scheduling, and battery simulation |
| [`SolarWise_Full_Pipeline.ipynb`](SolarWise_Full_Pipeline.ipynb) | Exploratory and end-to-end notebook workflow |
| [`damascus_nasa_hourly2.csv`](damascus_nasa_hourly2.csv) | Hourly solar and weather input data |
| [`appliances.csv`](appliances.csv) | Appliance power, duration, priority, and scheduling windows |
| [`solarwise_settings.json`](solarwise_settings.json) | Dataset, PV, battery, threshold, and evaluation settings |
| [`requirements.txt`](requirements.txt) | Python dependency list |

## How the analysis works

1. Load and validate the hourly weather dataset.
2. Engineer calendar, weather, clear-sky, and 24-hour lag features.
3. Compare linear regression, random forest, and gradient boosting models.
4. Select the best validation model using mean absolute error with a small
   tolerance for simpler model selection.
5. Convert forecast solar radiation into PV power using system capacity,
   efficiency, temperature effects, and inverter limits.
6. Schedule flexible appliances into available solar windows.
7. Simulate direct consumption, battery charging/discharging, curtailment, and
   unmet demand.

The default configuration uses Damascus data, a 3 kW PV system, and a 5 kWh
battery. Settings can be adjusted in
[`solarwise_settings.json`](solarwise_settings.json), while appliance behavior
can be edited in [`appliances.csv`](appliances.csv).

## Rebuilding the model

To force retraining instead of loading the local model artifact, use the
`train_or_load_model` function from [`pipeline.py`](pipeline.py) with
`force_retrain=True`. The generated `best_model.joblib` remains local and is
excluded from commits because it is a large, reproducible binary.

## Data provenance

The weather and solar-radiation fields are based on NASA POWER data prepared for
the Damascus analysis period. The included settings file records the UTC offset,
thresholds, evaluation period, and reported comparison values used by the
project.

## Development

The core pipeline is implemented as reusable Python functions, so it can be
tested or integrated without launching the UI. Keep generated files, virtual
environments, secrets, and local caches out of commits; see [`.gitignore`](.gitignore).

## License

No license has been declared yet. Until a license is added, all rights remain
with the repository owner.
