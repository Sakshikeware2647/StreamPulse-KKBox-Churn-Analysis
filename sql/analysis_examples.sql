-- StreamPulse case-study SQL examples (SQLite-style).
-- Run against data/processed/cleaned_user_level.csv after importing it as cleaned_users.
-- Source field names differ from the assignment; see README for mapping.

-- 1. Churn and retention
SELECT COUNT(*) AS labeled_users,
       ROUND(100.0 * AVG(is_churn), 2) AS churn_rate_pct,
       ROUND(100.0 * (1 - AVG(is_churn)), 2) AS retention_rate_pct
FROM cleaned_users;

-- 2. Engagement by churn outcome
SELECT churn_label,
       COUNT(DISTINCT msno) AS users,
       ROUND(AVG(log_days), 2) AS avg_active_days,
       ROUND(AVG(total_minutes), 2) AS avg_listening_minutes,
       ROUND(AVG(num_unq), 2) AS avg_unique_songs
FROM cleaned_users
GROUP BY churn_label;

-- 3. Health bands
SELECT CASE WHEN health_score < 40 THEN 'At Risk'
            WHEN health_score < 70 THEN 'Needs Attention'
            ELSE 'Healthy' END AS health_band,
       COUNT(*) AS users,
       ROUND(100.0 * AVG(is_churn), 2) AS churn_rate_pct
FROM cleaned_users
GROUP BY health_band
ORDER BY users DESC;

-- 4. DAU / MAU calculation is produced by the Python pipeline from daily logs.
-- MAU must be distinct users across the month, NOT the sum of daily DAU.
