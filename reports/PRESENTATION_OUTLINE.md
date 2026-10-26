# Executive presentation outline

Use these slides after running the pipeline and replacing all metrics with values from the output CSVs.

1. **Executive Summary** — cohort size, churn, retention, DAU/MAU, top 3 findings.
2. **Data Quality** — missing/invalid fields, deduplication, age and duration rules, log row counts.
3. **Engagement and Churn** — compare active days, listening minutes, unique songs by churn label.
4. **Retention Segmentation** — retention by payment-plan-duration proxy; clearly state true plan tiers are unavailable.
5. **Customer Health and Actions** — health-score distribution, risk intervention recommendations, metric limitations.

Do not present synthetic or placeholder KPIs as observed results. Use `data/processed/kpi_summary.csv` and `reports/executive_summary.md`.
