# Mamaearth Returns & Growth Intelligence Pipeline

Capstone project, Data Analytics with AI & Gen AI (E&ICT Academy, IIT Roorkee).

**The question:** where are returns really coming from, and what does revenue look like once the data is cleaned?

**The answer, in one line:** the verified revenue is **₹97,358.30** (₹2,501.90 less than the raw ₹99,860.20 because of 5 duplicate orders). COD orders are returned at **44.4%** against 14.7% for Card, and the problem is worst in **COD + Tier‑2 cities at 54.5%**. **March 2026 (₹20,318.90)** is the true peak month. January only looks like the peak because of two bulk orders.

The repo has three layers. Each layer feeds the next, and no layer reports a number it did not compute itself or receive from the layer before it:

```
data/*.csv ──► Part 1: SQL (sql/)          SQLite store + 9 reports on the RAW data
           └─► Part 2: pandas (analysis/)  clean → reconcile with Part 1 → EDA → charts
                                           └─► writes narrator/findings.json
                         Part 3: GenAI (narrator/) findings.json → SCR narrative (Gemini or offline)
```

---

## Repository structure

```
.
├── README.md
├── data/                       raw source CSVs, committed exactly as given (never hand-edited)
│   ├── customers.csv           45 rows
│   ├── products.csv            16 rows
│   └── orders.csv              180 rows (blanks, mixed casing, 5 duplicates, 2 bulk outliers)
├── sql/
│   ├── schema.sql              Task 1: CREATE TABLE with PK / FK / NOT NULL / DEFAULT
│   ├── seed_data.sql           Task 2: INSERT statements; blank cells → NULL
│   ├── generate_seed_data.py   regenerates seed_data.sql from data/*.csv
│   └── reports.sql             Task 3: reports a–i, real output pasted above each query
├── analysis/
│   ├── clean_and_eda.py        Part 2 Tasks 1–10; exports narrator/findings.json
│   └── visualize.py            Part 2 Task 11: the two PNG charts
├── visualizations/
│   ├── return_rate_by_payment.png
│   └── monthly_revenue_trend.png
└── narrator/
    ├── findings.json           written by clean_and_eda.py, never typed by hand
    ├── generate_narrative.py   Gemini SCR narrator + offline fallback + accuracy checker
    ├── sample_output.txt       a saved real Gemini run, checked by the checker
    └── offline_output.txt      output of the keyless offline template
```

Generated at run time and not committed: `mamaearth.db`, `analysis/output/` (the intermediate CSVs that `visualize.py` reads), and `.venv/`.

---

## Quick start

Requirements: **Python 3.9+**, Git, and the SQLite command-line tool (`sqlite3`) available on your PATH.

Clone the repository and enter the project directory:

```bash
git clone <this-repo-url>
cd <repo>
```

Create and activate a virtual environment, then install the dependencies directly. This repository does not require a `requirements.txt` file.

**Windows PowerShell**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install pandas matplotlib google-genai
```

**macOS / Linux**
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install pandas matplotlib google-genai
```

Run the three layers in order using the steps below. If you do not configure a Gemini API key, you can still run the narrator using its offline path.

## Step 1: SQL layer (Part 1)

```bash
sqlite3 mamaearth.db ".read sql/schema.sql"
sqlite3 mamaearth.db ".read sql/seed_data.sql"
sqlite3 -header -column mamaearth.db ".read sql/reports.sql"
```

Run these SQLite shell commands from the repository root in PowerShell, macOS, or Linux, with `sqlite3` installed and available on your PATH. `schema.sql` drops and recreates the tables, so the setup can be rerun without manually deleting the database.

* **Loading:** `seed_data.sql` uses plain `INSERT` statements generated from the CSVs by `python sql/generate_seed_data.py`. Blank `discount_pct` and `rating` cells become real SQL `NULL`. They do not become empty strings, so `COUNT(rating)` returns 165 and not 180. You can check this with `SELECT typeof(rating), COUNT(*) FROM orders GROUP BY 1;`, which returns `integer|165`, `null|15`.
* **Revenue formula:** `quantity * price * (1 - COALESCE(discount_pct, 0) / 100.0)`. The `100.0` is deliberate, because `/ 100` on an INT column is integer division in SQLite and silently returns 0.
* **Report results** (raw, uncleaned data):

| Report | Result |
|---|---|
| a) Totals | 180 orders, ₹99,860.20 revenue, ₹554.78 average order value |
| b) COUNT(*) vs COUNT(rating) | 180 / 165 / 15 unrated |
| c) Zero-order customers (LEFT JOIN and NOT IN) | C045 Vihaan (both queries agree) |
| d) Cities with return rate > 20% | Jaipur 42.1, Lucknow 30.6, Bangalore 24.2 |
| e) Top 5 by spend / ranks 3–5 via `LIMIT 3 OFFSET 2` | C043, C026, C008, C011, C042 / C008, C011, C042 |
| f) Revenue by category | Haircare 44,956.10 · Skincare 27,346.00 · Babycare 16,805.00 · PersonalCare 10,753.10 |
| g) Names starting with 'A' | 10 rows |
| h) Distinct acquisition sources | Ad, Organic, Referral, Social |
| i) loyalty_tier | Gold 28, Silver 17 |

## Step 2: Python / pandas layer (Part 2)

```bash
python analysis/clean_and_eda.py
python analysis/visualize.py
```

Run these commands from the repository root after installing the dependencies in the Quick start section. Task 5 of Part 2 writes the computed findings to `narrator/findings.json`; `visualize.py` generates the two PNG charts in `visualizations/`.

Part 2 reads the **raw CSVs directly**, not the database, so Parts 1 and 2 can run in either order. What it does, in the order that matters:

1. Load the data. Raw `orders.shape` is `(180, 9)`.
2. Standardise `payment_method`: 7 raw spellings become 3 (CARD 70, UPI 55, COD 55).
3. Drop duplicates on the natural key, **before** imputing. This drops O0176–O0180 and leaves `(175, 9)`.
4. Impute missing values: `discount_pct` NaN → 0 (12 rows) and `rating` NaN → median 3.0 (15 rows).
5. Merge and reconcile. The cleaned total is **₹97,358.30**. The ₹2,501.90 gap to Part 1's ₹99,860.20 is attributed exactly to the 5 dropped duplicates, whose values are summed independently as a check. The script prints this as a reconciliation note.
6. IQR outliers on quantity: Q1 1, Q3 2, bounds [-0.5, 3.5]. This **flags** two rows, O0011 (25 units) and O0098 (30 units), and keeps them in the data.
7. Hypothesis "COD returns more": **Confirmed**. COD 44.4%, UPI 18.9%, CARD 14.7%.
8. Segmentation: **COD + Tier‑2 at 54.5%** (22 orders), against 37.5% for Tier‑1 COD (32 orders).
9. Correlations: all six pairs are *negligible*. "Higher discounts reduce returns" is **Busted** (r ≈ ‑0.09).
10. Monthly revenue with and without outliers. January's ₹29,582.10 drops to ₹11,637.10 without them, which makes **March (₹20,318.90) the true peak**.

Both scripts are deterministic. Re-running them regenerates the same numbers and byte-identical PNGs.

## Step 3: GenAI narrator (Part 3)

Run this step **after** `analysis/clean_and_eda.py` has created `narrator/findings.json`.

### Option A: Run without a Gemini API key (offline)

This path needs no API key and no network connection for narration:

```bash
python narrator/generate_narrative.py --offline
```

The offline template uses the computed findings and produces a deterministic SCR-style narrative.

### Option B: Run with Gemini

Get a key from Google AI Studio: https://aistudio.google.com/apikey. Set it as an environment variable for your current terminal session. **Do not paste the key into source code or commit it to GitHub.**

**Windows PowerShell**
```powershell
$env:GEMINI_API_KEY = "YOUR_API_KEY"
python narrator/generate_narrative.py
```

**macOS / Linux**
```bash
export GEMINI_API_KEY="YOUR_API_KEY"
python narrator/generate_narrative.py
```

The script reads `narrator/findings.json` and saves the generated Gemini narrative to `narrator/sample_output.txt`. If no key is configured, or the API call fails, the script falls back to the offline narrative path.

### Check a saved narrative without calling Gemini

```bash
python narrator/generate_narrative.py --check narrator/sample_output.txt
```

The numeric accuracy checker reports PASS/FAIL for the five required figures: cleaned revenue ₹97,358.30, COD return rate 44.4%, COD + Tier-2 return rate 54.5%, duplicate revenue delta ₹2,501.90, and March revenue ₹20,318.90. The script exits with a non-zero status if a required figure fails the check.

Implementation notes:

- `generate_scr_narrative(findings)` uses `from google import genai`.
- The system instruction defines the analyst role, the Situation / Complication / Resolution structure, and the rule not to invent numbers. The user prompt is populated from `findings.json`.
- The generation settings use `temperature=0.0`, `max_output_tokens=4096`, `thinking_budget=1024`, and a 30-second request timeout.
- The API call is wrapped in `try/except` and returns a structured result; errors use the offline fallback.
- The model defaults to `gemini-3.8-flash`. To override it, set the `GEMINI_MODEL` environment variable in the current terminal session.

## How the data flows between layers

| From | To | What is passed |
|---|---|---|
| `data/*.csv` | `sql/seed_data.sql` | generated by `sql/generate_seed_data.py` |
| `data/*.csv` | `analysis/clean_and_eda.py` | read with `pd.read_csv` (independent of SQL) |
| Part 1 Report (a) ₹99,860.20 | Part 2 Task 5 | reconciled to the cleaned ₹97,358.30 (delta = 5 duplicates) |
| `clean_and_eda.py` | `analysis/output/*.csv` | read by `visualize.py` to draw the charts |
| `clean_and_eda.py` | `narrator/findings.json` | read by `generate_narrative.py` (Part 3) |

## Security

The API key is supplied through the `GEMINI_API_KEY` or `GOOGLE_API_KEY` environment variable and should never be written into source code or committed to the repository. The offline path needs no key at all.
