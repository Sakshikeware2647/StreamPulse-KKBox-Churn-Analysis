from __future__ import annotations
import argparse
import warnings
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

warnings.filterwarnings('ignore', category=FutureWarning)
ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data' / 'raw'
PROCESSED = ROOT / 'data' / 'processed'
OUTPUTS = ROOT / 'outputs'
CHARTS = OUTPUTS / 'charts'
REPORTS = ROOT / 'reports'
LABELS_PATH = RAW / 'train_v2.csv'
LOGS_PATH = RAW / 'user_logs_v2.csv'
TX_PATH = RAW / 'transactions_v2.csv'
MEMBERS_PATH = RAW / 'members_v3.csv'


def ensure_dirs():
    for p in (PROCESSED, OUTPUTS, CHARTS, REPORTS):
        p.mkdir(parents=True, exist_ok=True)


def require_file(path):
    if not path.exists():
        raise FileNotFoundError(f'Missing required file: {path}')


def norm(series):
    x = pd.to_numeric(series, errors='coerce')
    lo, hi = x.min(), x.max()
    if pd.isna(lo) or pd.isna(hi) or hi <= lo:
        return pd.Series(0.0, index=series.index)
    return ((x - lo) / (hi - lo)).fillna(0).clip(0, 1)


def main(log_rows=5000):
    ensure_dirs()
    for p in (LABELS_PATH, LOGS_PATH, TX_PATH, MEMBERS_PATH):
        require_file(p)

    print('1/6 Reading churn labels...', flush=True)
    labels = pd.read_csv(LABELS_PATH, usecols=['msno', 'is_churn'])
    raw_label_rows = len(labels)
    labels['is_churn'] = pd.to_numeric(labels['is_churn'], errors='coerce')
    labels = labels.dropna(subset=['msno', 'is_churn'])
    labels = labels[labels['is_churn'].isin([0, 1])].copy()
    labels['msno'] = labels['msno'].astype(str)
    labels['is_churn'] = labels['is_churn'].astype('int8')
    labels = labels.drop_duplicates('msno', keep='last')
    label_users = set(labels['msno'])
    print(f'   Labeled users retained: {len(labels):,}', flush=True)

    print('2/6 Reading member attributes...', flush=True)
    members = pd.read_csv(MEMBERS_PATH, low_memory=True)
    member_rows = len(members)
    keep = [c for c in ['msno', 'bd', 'gender', 'registered_via', 'registration_init_time'] if c in members]
    members = members[keep].copy()
    members['msno'] = members['msno'].astype(str)
    if 'bd' in members:
        members['bd'] = pd.to_numeric(members['bd'], errors='coerce')
        members.loc[~members['bd'].between(10, 100), 'bd'] = np.nan
    if 'registration_init_time' in members:
        members['registration_date'] = pd.to_datetime(
            members['registration_init_time'].astype('Int64').astype(str), format='%Y%m%d', errors='coerce')
        members.drop(columns=['registration_init_time'], inplace=True)
    members = members.drop_duplicates('msno', keep='last')

    print('3/6 Streaming activity logs; progress appears every 20 chunks...', flush=True)
    user_agg = {}
    daily_users = {}
    raw_log_rows = dup_log_rows = invalid_secs = 0
    log_columns = ['msno', 'date', 'num_25', 'num_50', 'num_75', 'num_985', 'num_100', 'num_unq', 'total_secs']
    counter_columns = ['num_25', 'num_50', 'num_75', 'num_985', 'num_100', 'num_unq']
    for chunk_no, chunk in enumerate(pd.read_csv(
        LOGS_PATH, usecols=lambda c: c in log_columns, chunksize=max(1000, log_rows), low_memory=True
    ), start=1):
        raw_log_rows += len(chunk)
        chunk['msno'] = chunk['msno'].astype(str)
        chunk['date'] = pd.to_datetime(chunk['date'].astype('Int64').astype(str), format='%Y%m%d', errors='coerce')
        for c in counter_columns + ['total_secs']:
            if c not in chunk:
                chunk[c] = np.nan
            chunk[c] = pd.to_numeric(chunk[c], errors='coerce')
        before = len(chunk)
        chunk = chunk.drop_duplicates(['msno', 'date'], keep='last')
        dup_log_rows += before - len(chunk)
        invalid_secs += int((chunk['total_secs'] < 0).sum())
        chunk.loc[(chunk['total_secs'] < 0) | (chunk['total_secs'] > 86400), 'total_secs'] = np.nan
        for c in counter_columns:
            chunk.loc[(chunk[c] < 0) | (chunk[c] > 10000), c] = np.nan
        # Critical: filter once per chunk, OUTSIDE the numeric-column loop.
        chunk = chunk.loc[chunk['msno'].isin(label_users) & chunk['date'].notna()].copy()
        if not chunk.empty:
            for dt, group in chunk.groupby('date', sort=False):
                daily_users.setdefault(dt, set()).update(group['msno'].unique())
            grouped = chunk.groupby('msno', sort=False).agg(
                log_days=('date', 'nunique'), total_secs=('total_secs', 'sum'), num_unq=('num_unq', 'sum'),
                num_25=('num_25', 'sum'), num_50=('num_50', 'sum'), num_75=('num_75', 'sum'),
                num_985=('num_985', 'sum'), num_100=('num_100', 'sum'),
                first_log_date=('date', 'min'), last_log_date=('date', 'max'))
            for uid, row in grouped.iterrows():
                cur = user_agg.setdefault(uid, {
                    'log_days': 0, 'total_secs': 0.0, 'num_unq': 0.0, 'num_25': 0.0,
                    'num_50': 0.0, 'num_75': 0.0, 'num_985': 0.0, 'num_100': 0.0,
                    'first_log_date': row['first_log_date'], 'last_log_date': row['last_log_date']})
                cur['log_days'] += int(row['log_days'])
                for c in ['total_secs'] + counter_columns:
                    if pd.notna(row[c]):
                        cur[c] += float(row[c])
                cur['first_log_date'] = min(cur['first_log_date'], row['first_log_date'])
                cur['last_log_date'] = max(cur['last_log_date'], row['last_log_date'])
        if chunk_no == 1 or chunk_no % 20 == 0:
            print(f'   Chunks: {chunk_no:,} | raw activity rows scanned: {raw_log_rows:,}', flush=True)

    print(f'   Activity scan finished: {raw_log_rows:,} rows.', flush=True)
    daily_df = pd.DataFrame([{'date': d, 'dau': len(u)} for d, u in daily_users.items()])
    if daily_df.empty:
        daily_df = pd.DataFrame(columns=['date', 'dau'])
    else:
        daily_df = daily_df.sort_values('date')
    daily_df.to_csv(PROCESSED / 'daily_active_users.csv', index=False, date_format='%Y-%m-%d')
    usage = pd.DataFrame.from_dict(user_agg, orient='index')
    usage.index.name = 'msno'
    usage = usage.reset_index()
    if usage.empty:
        usage = pd.DataFrame(columns=['msno', 'log_days', 'total_secs', 'num_unq', *counter_columns,
                                      'first_log_date', 'last_log_date'])
    usage['avg_session_mins_proxy'] = pd.to_numeric(usage.get('total_secs', 0), errors='coerce') / 60 / pd.to_numeric(
        usage.get('log_days', 1), errors='coerce').replace(0, np.nan)

    print('4/6 Aggregating transactions...', flush=True)
    tx_cols = ['msno', 'payment_method_id', 'payment_plan_days', 'plan_list_price', 'actual_amount_paid',
               'is_auto_renew', 'is_cancel', 'transaction_date', 'membership_expire_date']
    tx = pd.read_csv(TX_PATH, usecols=lambda c: c in tx_cols, low_memory=True)
    tx_rows = len(tx)
    for c in ['transaction_date', 'membership_expire_date']:
        if c in tx:
            tx[c + '_parsed'] = pd.to_datetime(tx[c].astype('Int64').astype(str), format='%Y%m%d', errors='coerce')
    for c in ['actual_amount_paid', 'plan_list_price', 'payment_plan_days', 'is_auto_renew', 'is_cancel']:
        if c in tx:
            tx[c] = pd.to_numeric(tx[c], errors='coerce')
    if 'transaction_date_parsed' in tx:
        tx = tx.sort_values('transaction_date_parsed')
    tx['msno'] = tx['msno'].astype(str)
    tx_user = tx.drop_duplicates('msno', keep='last').copy()
    tx_keep = [c for c in ['msno', 'payment_method_id', 'payment_plan_days', 'plan_list_price', 'actual_amount_paid',
                           'is_auto_renew', 'is_cancel', 'transaction_date_parsed', 'membership_expire_date_parsed'] if c in tx_user]
    tx_user = tx_user[tx_keep].rename(columns={'transaction_date_parsed': 'last_transaction_date',
                                               'membership_expire_date_parsed': 'last_expiry_date'})
    tx_user.to_csv(PROCESSED / 'latest_transaction_by_user.csv', index=False, date_format='%Y-%m-%d')

    print('5/6 Calculating metrics and writing tables...', flush=True)
    merged = labels.merge(usage, on='msno', how='left', validate='one_to_one')
    merged = merged.merge(members, on='msno', how='left', suffixes=('', '_member'))
    merged = merged.merge(tx_user, on='msno', how='left', suffixes=('', '_tx'))
    for c in ['log_days', 'total_secs'] + counter_columns:
        if c in merged:
            merged[c] = pd.to_numeric(merged[c], errors='coerce').fillna(0)
    merged['total_minutes'] = merged['total_secs'] / 60
    merged['health_score'] = (35 * norm(merged['log_days']) + 35 * norm(merged['total_minutes']) +
                              20 * norm(merged['num_unq']) + 10 * pd.to_numeric(
                                  merged.get('is_auto_renew', pd.Series(np.nan, index=merged.index)),
                                  errors='coerce').fillna(0).clip(0, 1)).clip(0, 100).round(1)
    merged['churn_label'] = merged['is_churn'].map({0: 'Retained', 1: 'Churned'})
    merged.to_csv(PROCESSED / 'cleaned_user_level.csv', index=False)
    churn_rate = float(labels['is_churn'].mean() * 100) if len(labels) else np.nan
    retention_rate = 100 - churn_rate
    latest_date = daily_df['date'].max() if len(daily_df) else pd.NaT
    month_start = latest_date.replace(day=1) if pd.notna(latest_date) else pd.NaT
    dau = int(daily_df.loc[daily_df['date'] == latest_date, 'dau'].sum()) if pd.notna(latest_date) else 0
    month_dates = set(daily_df.loc[daily_df['date'] >= month_start, 'date']) if pd.notna(month_start) else set()
    month_users = set()
    for dt in month_dates:
        month_users.update(daily_users.get(dt, set()))
    mau = len(month_users)
    stickiness = dau / mau * 100 if mau else np.nan
    arpu = pd.to_numeric(tx_user.get('actual_amount_paid', pd.Series(dtype=float)), errors='coerce').mean()
    ltv = arpu / (churn_rate / 100) if churn_rate and pd.notna(arpu) else np.nan

    if 'payment_plan_days' in tx_user:
        tx_user['plan_duration_band'] = pd.cut(pd.to_numeric(tx_user['payment_plan_days'], errors='coerce'),
            bins=[-1, 31, 100, 400, 10000], labels=['<=31 days', '32–100 days', '101–400 days', '>400 days'])
        plan_perf = tx_user.merge(labels, on='msno', how='inner').groupby('plan_duration_band', observed=False).agg(
            users=('msno', 'nunique'), churn_rate_pct=('is_churn', lambda x: x.mean() * 100)).reset_index()
        plan_perf['retention_rate_pct'] = 100 - plan_perf['churn_rate_pct']
    else:
        plan_perf = pd.DataFrame(columns=['plan_duration_band', 'users', 'churn_rate_pct', 'retention_rate_pct'])
    plan_perf.to_csv(PROCESSED / 'plan_retention_proxy.csv', index=False)
    engagement = merged.groupby('churn_label').agg(users=('msno', 'nunique'), avg_active_days=('log_days', 'mean'),
        avg_listening_minutes=('total_minutes', 'mean'), avg_unique_songs=('num_unq', 'mean'),
        avg_daily_minutes=('avg_session_mins_proxy', 'mean')).reset_index()
    engagement.to_csv(PROCESSED / 'engagement_by_churn.csv', index=False)
    health = merged.groupby(pd.cut(merged['health_score'], [-0.1, 39.9, 69.9, 100],
        labels=['At Risk', 'Needs Attention', 'Healthy']), observed=False).agg(
        users=('msno', 'nunique'), churn_rate_pct=('is_churn', lambda x: x.mean() * 100)).reset_index()
    health.to_csv(PROCESSED / 'health_distribution.csv', index=False)
    pd.DataFrame([
        ['Raw label rows', raw_label_rows], ['Labeled users retained', len(labels)],
        ['Churn rate (%)', round(churn_rate, 2)], ['Retention rate (%)', round(retention_rate, 2)],
        ['Latest observed activity date', str(latest_date.date()) if pd.notna(latest_date) else 'Unavailable'],
        ['DAU', dau], ['MAU (latest observed calendar month)', mau],
        ['DAU/MAU stickiness (%)', round(stickiness, 2) if pd.notna(stickiness) else 'N/A'],
        ['ARPU proxy (dataset currency)', round(arpu, 2) if pd.notna(arpu) else 'N/A'],
        ['LTV proxy (dataset currency)', round(ltv, 2) if pd.notna(ltv) else 'N/A'],
        ['NRR', 'Not computed: no reconciled opening/closing recurring-revenue bridge'],
        ['Raw user-log rows scanned', raw_log_rows], ['Duplicate rows removed within chunks', dup_log_rows],
        ['Invalid negative duration rows flagged', invalid_secs], ['Member rows in source', member_rows],
        ['Transaction rows in source', tx_rows]
    ], columns=['metric', 'value']).to_csv(PROCESSED / 'kpi_summary.csv', index=False)
    pd.DataFrame([
        ['Missing/invalid churn label', 'is_churn null or outside {0,1}', 'Excluded from labeled cohort'],
        ['Duplicate activity logs', 'Repeated msno + date within a chunk', 'Keep last within chunk; cross-chunk duplicates may remain'],
        ['Invalid listening duration', 'total_secs < 0 or > 86400', 'Set to missing'],
        ['Invalid play counters', 'Counter < 0 or > 10000', 'Set to missing'],
        ['Implausible age', 'bd outside 10–100', 'Set to missing'],
        ['Missing activity', 'No matched user log', 'Kept as zero observed activity; not proof of no real use'],
        ['Support tickets', 'Not present in source', 'Not fabricated; excluded from health score'],
        ['Subscription tier', 'Basic/Pro/Enterprise not present', 'Payment-duration band is only a proxy']
    ], columns=['defect', 'detection', 'action']).to_csv(PROCESSED / 'data_cleaning_log.csv', index=False)

    print('6/6 Creating charts and executive summary...', flush=True)
    if not daily_df.empty:
        fig, ax = plt.subplots(figsize=(10, 4.5)); recent = daily_df.tail(45)
        ax.plot(recent['date'], recent['dau'], marker='o'); ax.set_title('KKBox Daily Active Users — Last 45 Observed Days')
        ax.set_ylabel('Distinct active users'); fig.autofmt_xdate(); fig.tight_layout()
        fig.savefig(CHARTS / 'daily_active_users.png', dpi=150); plt.close(fig)
    if not plan_perf.empty:
        fig, ax = plt.subplots(figsize=(8, 4.5)); ax.bar(plan_perf['plan_duration_band'].astype(str), plan_perf['retention_rate_pct'])
        ax.set_title('Retention by Payment Duration Proxy'); ax.set_ylabel('Retention (%)'); ax.tick_params(axis='x', rotation=15)
        fig.tight_layout(); fig.savefig(CHARTS / 'retention_by_plan_proxy.png', dpi=150); plt.close(fig)
    fig, ax = plt.subplots(figsize=(8, 4.5)); ax.hist(merged['health_score'].dropna(), bins=20)
    ax.set_title('Customer Health Index Distribution (heuristic)'); ax.set_xlabel('Score (0–100)'); ax.set_ylabel('Users')
    fig.tight_layout(); fig.savefig(CHARTS / 'health_distribution.png', dpi=150); plt.close(fig)
    if not engagement.empty:
        ax = engagement.set_index('churn_label')[['avg_active_days', 'avg_listening_minutes', 'avg_unique_songs']].plot(kind='bar', figsize=(9, 5))
        ax.set_title('Engagement Metrics by Churn Outcome'); ax.set_ylabel('Average per user'); plt.xticks(rotation=0); plt.tight_layout()
        plt.savefig(CHARTS / 'engagement_by_churn.png', dpi=150); plt.close()
    fig, axes = plt.subplots(2, 2, figsize=(12, 8)); fig.suptitle('StreamPulse Case Study | KKBox Churn & Engagement', fontweight='bold')
    axes[0, 0].axis('off'); axes[0, 0].text(.02, .95, f'Labeled users: {len(labels):,}\nChurn: {churn_rate:.2f}%\nRetention: {retention_rate:.2f}%\nDAU: {dau:,}\nMAU: {mau:,}\nStickiness: {stickiness:.2f}%\nARPU proxy: {arpu:.2f}', va='top', fontsize=12)
    if not daily_df.empty:
        axes[0, 1].plot(daily_df.tail(45)['date'], daily_df.tail(45)['dau']); axes[0, 1].set_title('Daily active users'); axes[0, 1].tick_params(axis='x', rotation=30)
    if not plan_perf.empty:
        axes[1, 0].bar(plan_perf['plan_duration_band'].astype(str), plan_perf['retention_rate_pct']); axes[1, 0].set_title('Retention by duration proxy'); axes[1, 0].tick_params(axis='x', rotation=15)
    axes[1, 1].hist(merged['health_score'].dropna(), bins=20); axes[1, 1].set_title('Health index distribution')
    fig.tight_layout(rect=[0, 0, 1, .95]); fig.savefig(OUTPUTS / 'dashboard.png', dpi=160); plt.close(fig)
    best = plan_perf.sort_values('retention_rate_pct', ascending=False).head(1)
    best_text = f"{best.iloc[0]['plan_duration_band']} ({best.iloc[0]['retention_rate_pct']:.2f}%)" if len(best) else 'Unavailable'
    eng_text = '\n'.join(f'- **{r.churn_label}:** {int(r.users):,} users; average active days {r.avg_active_days:.2f}; listening minutes {r.avg_listening_minutes:.2f}; unique songs {r.avg_unique_songs:.2f}.' for r in engagement.itertuples())
    report = f'''# StreamPulse — Executive Summary (KKBox case-study edition)\n\n**Source:** KKBox Churn Prediction Challenge on Kaggle. This is an adapted case study, not StreamPulse production data.\n\n## Top KPIs\n- Labeled cohort: **{len(labels):,}**\n- Churn rate: **{churn_rate:.2f}%**; retention rate: **{retention_rate:.2f}%**\n- DAU: **{dau:,}**; latest observed activity date: {str(latest_date.date()) if pd.notna(latest_date) else 'unavailable'}\n- MAU: **{mau:,}**; stickiness: **{stickiness:.2f}%**\n- ARPU proxy: **{arpu:.2f}**; LTV proxy: **{ltv:.2f}** (dataset currency)\n- NRR: not computed; the required recurring-revenue bridge is unavailable.\n\n## Plan performance proxy\nNo Basic/Pro/Enterprise tier exists in the source. Payment duration bands are only a proxy. Highest observed retention proxy: **{best_text}**.\n\n## Engagement by churn outcome\n{eng_text}\n\n## Recommendations\n1. Flag declining active days, listening time, and unique-song activity for early retention outreach.\n2. Test renewal reminders for non-auto-renewing users with a controlled experiment.\n3. Segment using observed payment duration and renewal behavior, not unavailable StreamPulse tiers.\n4. Add approved support-ticket data before using support volume in a health index.\n\n## Data-quality limitations\nSee `data/processed/data_cleaning_log.csv`. Duplicate user-date records are removed within each chunk only; duplicates crossing chunk boundaries may remain. The source has no support-ticket field or StreamPulse plan tiers. The health score is a heuristic, not a validated churn probability.\n'''
    (REPORTS / 'executive_summary.md').write_text(report, encoding='utf-8')
    print('\nANALYSIS COMPLETE', flush=True)
    print(f'KPI table: {PROCESSED / "kpi_summary.csv"}', flush=True)
    print(f'Dashboard: {OUTPUTS / "dashboard.png"}', flush=True)
    print(f'Executive summary: {REPORTS / "executive_summary.md"}', flush=True)
    print('Note: KKBox is a proxy dataset, not actual StreamPulse data.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='KKBox churn and engagement analysis')
    parser.add_argument('--log-rows', type=int, default=5000, help='Activity rows per chunk (default 5000)')
    args = parser.parse_args()
    main(args.log_rows)


    # 18 million activity log rows 
    # I used chunk-based processing to 
    # reduce memory requirements and 
    # aggregated the data into customer-level 
    # and daily summaries.
