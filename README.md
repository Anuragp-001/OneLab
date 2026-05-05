# 🧮 Onelab — Payments Reconciliation Dashboard

> _"A payments company's books don't balance at month end. They know every transaction their platform processed. They know what the bank says actually arrived. The two should match. They don't. Find out why."_

A complete, runnable solution to the Onelab payments reconciliation assessment. The system generates synthetic transactions and bank settlements, plants four canonical "gap" types into the data, and runs a reconciliation engine that finds and visualises every gap.

---

## ✨ What's inside

| Layer | Tech | Files |
|---|---|---|
| **Data generation** | Faker, NumPy, Pandas | `src/data_generator.py` |
| **Gap planting (4 types)** | Pandas | `src/gap_types.py` |
| **Reconciliation engine** | Pandas (vectorised) | `src/reconciliation.py` |
| **Analytics & charts** | Plotly | `src/analytics.py`, `src/visualizations.py` |
| **UI (multi-page)** | Streamlit | `app.py` + `pages/*.py` |
| **Tests** | pytest | `tests/*.py` |

The four planted gap types (per the assessment brief):

1. 🌙 **Late settlement** — transaction in April, settled in May
2. 🪙 **Rounding difference** — sub-dollar mismatch invisible per row, visible when summed
3. ♻️ **Duplicate entry** — same transaction settled twice by the bank
4. 🚫 **Orphan refund** — refund whose original sale doesn't exist

---

## 🚀 Quick start (3 commands)

```bash
pip install -r requirements.txt
cp .env.example .env
streamlit run app.py
```

Then open <http://localhost:8501> in your browser.

---

## 🛠 Setup with `uv` (Astral) — recommended

`uv` is ~10–100× faster than pip. Use it if you have it installed.

### Step 1 — Install `uv`

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### Step 2 — Create the virtual environment with Python 3.11

```bash
# macOS / Linux & Windows (PowerShell)
uv venv --python 3.11
```

### Step 3 — Activate the environment

```bash
# macOS / Linux
source .venv/bin/activate

# Windows (PowerShell)
.venv\Scripts\Activate.ps1
```

### Step 4 — Install dependencies

```bash
uv pip install -r requirements.txt
```

### Step 5 — Verify installation

```bash
python -c "import streamlit, pandas, plotly, faker; print('OK')"
# Expected output: OK
```

### Step 6 — Run the Streamlit app

```bash
streamlit run app.py
```

The app opens at <http://localhost:8501>. Use the sidebar to regenerate the dataset with new parameters at any time.

### Step 7 — Run the test suite

```bash
pytest -v
```

Expected: all tests pass (✅ green).

---

## 🐍 Setup with plain Python venv (alternative)

```bash
# macOS / Linux
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

```powershell
# Windows (PowerShell)
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

---

## 🌐 Deploying to Streamlit Community Cloud

### Step 1 — Push to GitHub

```bash
cd onelab-reconciliation
git init
git add .
git commit -m "Initial commit — Onelab reconciliation"
git branch -M main
git remote add origin https://github.com/<your-username>/onelab-reconciliation.git
git push -u origin main
```

### Step 2 — Sign up at Streamlit Cloud

Go to <https://share.streamlit.io> and sign in with your GitHub account. Authorise the Streamlit GitHub app.

### Step 3 — Create a new app

- Click **"New app"**
- Repository: `<your-username>/onelab-reconciliation`
- Branch: `main`
- Main file path: `app.py`
- Python version: `3.11`

### Step 4 — Configure secrets (optional)

If you add API keys later, paste them under **"Advanced settings → Secrets"** in TOML format:

```toml
DATA_SEED = "42"
NUM_TRANSACTIONS = "600"
RECON_MONTH = "4"
RECON_YEAR = "2026"
ANTHROPIC_API_KEY = "sk-..."
```

The `python-dotenv` setup in `src/state.py` reads from environment variables, and Streamlit Cloud injects secrets as env vars automatically.

### Step 5 — Deploy

Click **"Deploy"**. First boot takes ~2–3 minutes (Streamlit installs dependencies). Once live, you'll get a URL like:

```
https://<your-username>-onelab-reconciliation-app-<hash>.streamlit.app
```

### Step 6 — Common deployment errors and fixes

| Error | Fix |
|---|---|
| `ModuleNotFoundError: src` | Streamlit Cloud needs the working dir to be the repo root — make sure `app.py` is at the top level (it is). |
| Slow first load | Normal — first run installs deps. Subsequent runs are warm-cached. |
| App crashes on regenerate | Check the **Manage app** logs in Streamlit Cloud. Almost always a missing dependency in `requirements.txt`. |
| `streamlit: command not found` locally | You need to activate the venv: `source .venv/bin/activate`. |

---

## 🧪 Test cases

Run all tests with `pytest -v`. The suite covers:

### Data generator (`tests/test_data_generator.py`)
- Returns two DataFrames
- All transactions in target month
- Settlements 1:1 with transactions
- Sale amounts within $5–$5000 range
- Refunds have negative amounts and link to real originals
- Currency is USD throughout
- Seed is deterministic
- Settlement lag is realistic (T+1 to T+3)
- Minimum 500 transactions for meaningful analysis

### Gap detection (`tests/test_gap_detection.py`) — the most important
For each of the 4 planted gap types, the suite asserts both that the gap is correctly **planted** in the input AND that the engine **detects** the same `transaction_id` in its output.

| Gap | Planted condition | Detected by |
|---|---|---|
| **Late settlement** | `settlement.month != April` | `txn.month == period AND settlement.month != period` |
| **Rounding diff** | `abs(amount − settled) == $0.01` | `0.001 < abs(diff) < 1.00` |
| **Duplicate** | 2 settlement rows for one txn | `groupby(txn_id).size() > 1` |
| **Orphan refund** | refund's `original_transaction_id` not in txn table | `refund AND original_id NOT IN ids` |

Plus integration tests:
- All 4 gap types present in result
- Planted IDs are distinct
- Match rate is >95% but <100% (mostly clean, a few gaps)

### Reconciliation engine (`tests/test_reconciliation.py`)
- Returns a structured `ReconciliationResult`
- Summary contains all required keys
- Match rate is a valid percentage
- Amount-difference is arithmetically correct
- **Clean data yields 100% match rate** (no false positives)
- Full report is CSV-serialisable
- No transaction is double-classified (matched ∩ gap = ∅)

---

## 📁 Project structure

```
onelab-reconciliation/
├── app.py                       ← Streamlit entry point (home page)
├── requirements.txt             ← Pinned dependencies
├── .env.example                 ← Config template
├── .env                         ← Local config (in .gitignore in real use)
├── .gitignore
├── README.md
├── .streamlit/
│   └── config.toml              ← Dark theme + server settings
├── data/                        ← Generated CSVs land here on download
├── src/
│   ├── __init__.py
│   ├── data_generator.py        ← Synthetic transactions + settlements
│   ├── gap_types.py             ← Plants the 4 gap types
│   ├── reconciliation.py        ← Vectorised matching + gap detection
│   ├── analytics.py             ← Aggregations for charts
│   ├── visualizations.py        ← All Plotly chart builders
│   └── state.py                 ← Streamlit session state + theming
├── pages/
│   ├── 1_Data_Overview.py       ← Inspect both datasets
│   ├── 2_Reconciliation.py      ← Engine in action + waterfall + heatmap
│   ├── 3_Gap_Analysis.py        ← Drill-down on each of the 4 gaps
│   └── 4_Summary_Report.py      ← Executive summary + CSV download
└── tests/
    ├── __init__.py
    ├── test_data_generator.py
    ├── test_gap_detection.py    ← End-to-end traceability of planted gaps
    └── test_reconciliation.py
```

---

## ⚠️ Production limitations (the 3 sentences the assessment asks for)

1. **Currency & FX**: This system reconciles only USD. In production, a payments platform deals with multi-currency settlements where FX-conversion timing, the spread between mid-rate and settlement-rate, and per-currency rounding modes (ISO-4217) would create an entire additional class of gaps not modelled here.

2. **Identifier fragility**: Real banks frequently don't echo the platform's `transaction_id` back. Settlements arrive with a bank reference, an acquirer batch ID, or only an aggregated batch total. A production engine needs fuzzy matching by amount + window + merchant + last-4 of card, with a tie-breaking ranker — not a clean inner-join.

3. **State is missing**: This system models a single point-in-time reconciliation. Real money flows include chargebacks, partial refunds, fee deductions, hold-and-release patterns, and interchange/scheme fees that net against settlement amounts — none of which are modelled here.

---

## 📜 License

MIT — built for the Onelab AI Fitness Assessment, 2026.
