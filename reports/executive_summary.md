# StreamPulse — Executive Summary (KKBox case-study edition)

**Source:** KKBox Churn Prediction Challenge on Kaggle. This is an adapted case study, not StreamPulse production data.

## Top KPIs
- Labeled cohort: **970,960**
- Churn rate: **8.99%**; retention rate: **91.01%**
- DAU: **416,825**; latest observed activity date: 2017-03-31
- MAU: **754,551**; stickiness: **55.24%**
- ARPU proxy: **297.17**; LTV proxy: **3303.97** (dataset currency)
- NRR: not computed; the required recurring-revenue bridge is unavailable.

## Plan performance proxy
No Basic/Pro/Enterprise tier exists in the source. Payment duration bands are only a proxy. Highest observed retention proxy: **<=31 days (95.56%)**.

## Engagement by churn outcome
- **Churned:** 87,330 users; average active days 12.33; listening minutes 1625.69; unique songs 366.16.
- **Retained:** 883,630 users; average active days 14.10; listening minutes 1821.08; unique songs 400.92.

## Recommendations
1. Flag declining active days, listening time, and unique-song activity for early retention outreach.
2. Test renewal reminders for non-auto-renewing users with a controlled experiment.
3. Segment using observed payment duration and renewal behavior, not unavailable StreamPulse tiers.
4. Add approved support-ticket data before using support volume in a health index.

## Data-quality limitations
See `data/processed/data_cleaning_log.csv`. Duplicate user-date records are removed within each chunk only; duplicates crossing chunk boundaries may remain. The source has no support-ticket field or StreamPulse plan tiers. The health score is a heuristic, not a validated churn probability.
