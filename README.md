# StreamPulse — Churn & Engagement Analytics (Kaggle dataset edition)

**Dataset source:** [KKBox Churn Prediction Challenge — Kaggle](https://www.kaggle.com/competitions/kkbox-churn-prediction-challenge/data)  
**Purpose:** Portalwiz Data Analyst Intern assignment  
**Stack:** Python, pandas, Matplotlib, SQL, PowerPoint/PDF report generation

## Important: dataset access
This project uses the public Kaggle competition dataset, not fabricated customer records. Kaggle requires sign-in and acceptance of competition rules. Download the files yourself and put them under `data/raw/`. The dataset is large; this project processes user logs in chunks to avoid loading the entire file into RAM.

Required files:
- `train_v2.csv` (or `train.csv`) — user ID and churn label
- `user_logs_v2.csv` (or `user_logs.csv`) — daily usage telemetry
- `transactions_v2.csv` (or `transactions.csv`) — subscription/payment history
- `members_v3.csv` (or `members.csv`) — member/account data

Official source: https://www.kaggle.com/competitions/kkbox-churn-prediction-challenge/data  
Dataset context and columns: https://www.kaggle.com/competitions/customer-retention-datathon-riyadh-edition/data

## 60-minute execution path
1. Sign in to Kaggle, open the official data page, and accept the rules.
2. Download the four files listed above. Extract `.7z` archives with 7-Zip if needed.
3. Copy the CSVs to `data/raw/`. Do not rename columns.
4. In terminal: `py -m venv .venv` (Windows), then `.venv\\Scripts\\activate`, then `pip install -r requirements.txt`.
5. Run: `python src/analyze.py --log-rows 500000`.
6. Review `data/processed/`, `outputs/dashboard.png`, `reports/executive_summary.md`, and generated report/deck if enabled.

## Dataset fields and mapping to assignment
- `msno` → user identifier
- `is_churn` → churn label (1 = did not renew within 30 days; 0 = renewed)
- `date` → activity date
- `total_secs` → total listening seconds; converted to minutes
- `num_unq`, `num_25`, `num_50`, `num_75`, `num_985`, `num_100` → usage proxies
- `payment_plan_days`, `plan_list_price`, `actual_amount_paid`, `is_auto_renew`, `is_cancel`, transaction/expiry dates → subscription and revenue proxies
- member registration and demographics → account attributes

This is a music-streaming subscription dataset, not productivity/video telemetry. Support tickets are not available in the core files; do not fabricate them. Use the provided behavioral fields as engagement proxies.

## Metrics and limitations
- DAU: unique `msno` with a valid log on the latest observed `date`.
- MAU: unique `msno` with a valid log in the latest calendar month available in user logs.
- Stickiness: latest observed DAU / latest-calendar-month MAU × 100. State that this is a snapshot ratio.
- Churn rate: mean of `is_churn` across labeled cohort.
- Retention rate: 1 − churn rate.
- ARPU proxy: average `actual_amount_paid` from the latest transaction per user in the labeled cohort. Currency is dataset-defined (NTD); do not label it USD.
- LTV proxy: ARPU / churn rate. This is a rough proxy, not finance-grade LTV.
- NRR: not fully computable from the provided tables as a finance-grade metric because a consistent opening MRR cohort with expansion/contraction/reactivation movements is not directly supplied. Report an explicitly labeled revenue-retention proxy only if clearly defined; the code reports `NRR = Not computed` rather than inventing values.
- Health index: 0–100 heuristic based on active days, listening duration, unique songs, and auto-renew where available. Support-ticket weighting is omitted because the source has no support-ticket field.
- “30-day churn”: the label means no valid renewal within 30 days after expiry. This is not identical to a cancellation event.
- The original logs cover historical time, not the current 90 days. Clearly state the observed data period in your report.

## Project outputs
- Cleaned/aggregated user-level dataset
- Data quality and cleaning log
- KPI summary
- Plan/transaction proxy analysis
- Engagement comparison by churn label
- User health index distribution
- Dashboard and chart images
- Executive summary markdown
- SQL examples

## Data ethics / attribution
Attribute the source to KKBox and the Kaggle competition. Follow Kaggle competition terms and any dataset-specific license/rules. Do not claim these records are StreamPulse's real customers. The business narrative is a case-study adaptation.
