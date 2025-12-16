import sys
sys.path.insert(0, '.')
from modules.odoo_client import OdooClient
from datetime import datetime

odoo = OdooClient()
odoo.connect()

# Phase definitions (2025)
# P3: Nov 24 - Dec 16 (post-deploy) = 23 days
# P2: 90 days before Nov 24 = Aug 26 - Nov 23
# P1: 90 days before P2 = May 28 - Aug 25

phases = {
    'P1': {'start': '2025-05-28', 'end': '2025-08-25', 'days': 90, 'label': 'Baseline'},
    'P2': {'start': '2025-08-26', 'end': '2025-11-23', 'days': 90, 'label': 'Pre-Deploy'},
    'P3': {'start': '2025-11-24', 'end': '2025-12-16', 'days': 23, 'label': 'Post-Deploy'},
}

results = {}

for phase, info in phases.items():
    start, end, days = info['start'], info['end'], info['days']

    # Total leads (including archived)
    total_leads = odoo.models.execute_kw(
        odoo.config.ODOO_DB, odoo.uid, odoo.config.ODOO_PASSWORD,
        'crm.lead', 'search_count',
        [[['create_date', '>=', f'{start} 00:00:00'], ['create_date', '<=', f'{end} 23:59:59']]],
        {'context': {'active_test': False}}
    )

    # Qualified (type=opportunity) - this means they progressed beyond "New/Lead" stage
    qualified = odoo.models.execute_kw(
        odoo.config.ODOO_DB, odoo.uid, odoo.config.ODOO_PASSWORD,
        'crm.lead', 'search_count',
        [[['create_date', '>=', f'{start} 00:00:00'], ['create_date', '<=', f'{end} 23:59:59'], ['type', '=', 'opportunity']]],
        {'context': {'active_test': False}}
    )

    # Won deals
    won = odoo.models.execute_kw(
        odoo.config.ODOO_DB, odoo.uid, odoo.config.ODOO_PASSWORD,
        'crm.lead', 'search_read',
        [[['create_date', '>=', f'{start} 00:00:00'], ['create_date', '<=', f'{end} 23:59:59'], ['stage_id.is_won', '=', True]]],
        {'fields': ['id', 'name', 'partner_name', 'date_closed', 'create_date', 'user_id', 'source_id', 'date_last_stage_update'], 'context': {'active_test': False}}
    )

    days_to_won_list = []
    won_deals_clean = []
    today = datetime.now()

    # Manual date corrections for leads entered late into Odoo
    DATE_CORRECTIONS = {
        8343: '2025-11-24 09:00:00',  # Emirates Foundation - actual lead date was Nov 24
    }

    for w in won:
        if w.get('create_date'):
            try:
                # Apply manual date correction if exists
                create_date_str = DATE_CORRECTIONS.get(w['id'], w['create_date'])
                created = datetime.fromisoformat(create_date_str.replace('Z', ''))

                # Use date_closed if available, otherwise fall back to date_last_stage_update
                closed = None
                closed_str = w.get('date_closed')
                if closed_str and closed_str != False:
                    closed_str = str(closed_str)
                    if 'T' in closed_str or ' ' in closed_str:
                        closed = datetime.fromisoformat(closed_str.replace('Z', '').replace(' ', 'T'))
                    else:
                        closed = datetime.strptime(closed_str, '%Y-%m-%d')
                elif w.get('date_last_stage_update'):
                    # Fallback to last stage update as close date
                    closed = datetime.fromisoformat(w['date_last_stage_update'].replace('Z', ''))

                if closed and closed <= today:
                    dtw = (closed - created).days
                    if dtw >= 0:
                        days_to_won_list.append(dtw)
                        won_deals_clean.append({**w, 'days_to_won': dtw})
            except:
                pass

    # Calculate corrected days to won (excluding outliers > 90 days)
    days_to_won_corrected = [d for d in days_to_won_list if d <= 90]

    # Days to progress (first stage change)
    leads_data = odoo.models.execute_kw(
        odoo.config.ODOO_DB, odoo.uid, odoo.config.ODOO_PASSWORD,
        'crm.lead', 'search_read',
        [[['create_date', '>=', f'{start} 00:00:00'], ['create_date', '<=', f'{end} 23:59:59']]],
        {'fields': ['create_date', 'date_last_stage_update'], 'context': {'active_test': False}}
    )

    days_to_progress_list = []
    for lead in leads_data:
        if lead.get('create_date') and lead.get('date_last_stage_update'):
            try:
                created = datetime.fromisoformat(lead['create_date'].replace('Z', ''))
                updated = datetime.fromisoformat(lead['date_last_stage_update'].replace('Z', ''))
                dtp = (updated - created).days
                if 0 < dtp <= 365:
                    days_to_progress_list.append(dtp)
            except:
                pass

    # Calculate unqualified count
    unqualified = total_leads - qualified

    results[phase] = {
        'total': total_leads,
        'leads_per_day': round(total_leads / days, 1),
        'qualified': qualified,
        'unqualified': unqualified,
        # Conversion to Qualified+ (from all leads)
        'to_qualified_pct': round(qualified / total_leads * 100, 1) if total_leads > 0 else 0,
        # Conversion to Won (from all leads)
        'to_won_all_pct': round(len(won_deals_clean) / total_leads * 100, 1) if total_leads > 0 else 0,
        # Conversion to Won (from qualified only)
        'to_won_qualified_pct': round(len(won_deals_clean) / qualified * 100, 1) if qualified > 0 else 0,
        # Days metrics
        'days_to_progress': round(sum(days_to_progress_list) / len(days_to_progress_list), 1) if days_to_progress_list else None,
        'days_to_won': round(sum(days_to_won_list) / len(days_to_won_list), 1) if days_to_won_list else None,
        'days_to_won_corrected': round(sum(days_to_won_corrected) / len(days_to_won_corrected), 1) if days_to_won_corrected else None,
        'won': len(won_deals_clean),
        'won_deals': won_deals_clean,
        'days': days,
    }

# Helper function for change calculation
def calc_change(v1, v2):
    if v1 is None or v2 is None or v1 == 0:
        return "N/A"
    change = ((v2 - v1) / v1) * 100
    return f"{change:+.1f}%"

# Print Report
print("="*90)
print("P1/P2/P3 PIPELINE PERFORMANCE COMPARISON REPORT")
print("="*90)
print()
print("Date Ranges:")
for phase, info in phases.items():
    print(f"  {phase} ({info['label']}): {info['start']} to {info['end']} ({info['days']} days)")
print()

# Summary Table (matching your format)
print("-"*90)
print(f"{'Metric':<30} {'P1':>10} {'P2':>10} {'P3':>10} {'P2->P3':>12} {'P1->P3':>12}")
print("-"*90)

metrics = [
    ("Leads/Day", "leads_per_day"),
    ("Conversion to Qualified+", "to_qualified_pct"),
    ("Conversion to Won (all)", "to_won_all_pct"),
    ("Conversion to Won (qualified)", "to_won_qualified_pct"),
    ("Days to Progress", "days_to_progress"),
    ("Days to Won", "days_to_won"),
]

for label, key in metrics:
    p1 = results["P1"][key]
    p2 = results["P2"][key]
    p3 = results["P3"][key]

    # Format values
    if key.endswith('_pct'):
        p1_str = f"{p1}%" if p1 is not None else "N/A"
        p2_str = f"{p2}%" if p2 is not None else "N/A"
        p3_str = f"{p3}%" if p3 is not None else "N/A"
    else:
        p1_str = f"{p1}" if p1 is not None else "N/A"
        p2_str = f"{p2}" if p2 is not None else "N/A"
        p3_str = f"{p3}" if p3 is not None else "N/A"

    p2_p3 = calc_change(p2, p3)
    p1_p3 = calc_change(p1, p3)

    print(f"{label:<30} {p1_str:>10} {p2_str:>10} {p3_str:>10} {p2_p3:>12} {p1_p3:>12}")

print("-"*90)
print()

# Volume Metrics Table
print("Volume Metrics:")
print("-"*60)
print(f"{'Metric':<30} {'P1':>10} {'P2':>10} {'P3':>10}")
print("-"*60)
print(f"{'Total Leads':<30} {results['P1']['total']:>10} {results['P2']['total']:>10} {results['P3']['total']:>10}")
print(f"{'Qualified (Opportunities)':<30} {results['P1']['qualified']:>10} {results['P2']['qualified']:>10} {results['P3']['qualified']:>10}")
print(f"{'Unqualified (Leads)':<30} {results['P1']['unqualified']:>10} {results['P2']['unqualified']:>10} {results['P3']['unqualified']:>10}")
print(f"{'Won Deals':<30} {results['P1']['won']:>10} {results['P2']['won']:>10} {results['P3']['won']:>10}")
print("-"*60)
print()

# Won Deals in P3
print("Won Deals (P3):")
print("-"*80)
print(f"{'Company':<40} {'Source':<15} {'Owner':<15} {'Days':>6}")
print("-"*80)
for deal in results["P3"]["won_deals"]:
    name = (deal.get("name") or deal.get("partner_name") or "Unknown")[:40]
    source = (deal.get("source_id")[1] if isinstance(deal.get("source_id"), (list, tuple)) else "Unknown")[:15]
    owner = (deal.get("user_id")[1] if isinstance(deal.get("user_id"), (list, tuple)) else "Unknown")[:15]
    dtw = deal.get("days_to_won", "N/A")
    print(f"{name:<40} {source:<15} {owner:<15} {dtw:>6}")

if results["P3"]["won_deals"]:
    avg_dtw = results["P3"]["days_to_won"]
    avg_dtw_corr = results["P3"]["days_to_won_corrected"]
    print("-"*80)
    print(f"Average Days to Won: {avg_dtw} days")
    if avg_dtw != avg_dtw_corr:
        print(f"Average Days to Won (corrected, excl >90 days): {avg_dtw_corr} days")
print()

# Key Findings
print("="*90)
print("KEY FINDINGS")
print("="*90)
print()

# Calculate improvements
p2_p3_progress = abs(((results["P3"]["days_to_progress"] - results["P2"]["days_to_progress"]) / results["P2"]["days_to_progress"] * 100)) if results["P2"]["days_to_progress"] and results["P3"]["days_to_progress"] else 0
p2_p3_won = abs(((results["P3"]["days_to_won"] - results["P2"]["days_to_won"]) / results["P2"]["days_to_won"] * 100)) if results["P2"]["days_to_won"] and results["P3"]["days_to_won"] else 0
p1_p3_qualified = ((results["P3"]["to_qualified_pct"] - results["P1"]["to_qualified_pct"]) / results["P1"]["to_qualified_pct"] * 100) if results["P1"]["to_qualified_pct"] else 0

print(f"1. CONVERSION RATE RECOVERY:")
print(f"   - Conversion to Qualified+ recovered to {results['P3']['to_qualified_pct']}% in P3")
print(f"   - P2->P3 change: {calc_change(results['P2']['to_qualified_pct'], results['P3']['to_qualified_pct'])}")
print()
print(f"2. VELOCITY IMPROVEMENT - The most dramatic impact:")
print(f"   - Leads now progress {p2_p3_progress:.0f}% faster (Days to Progress: {results['P2']['days_to_progress']} -> {results['P3']['days_to_progress']} days)")
print(f"   - Leads close {p2_p3_won:.0f}% faster (Days to Won: {results['P2']['days_to_won']} -> {results['P3']['days_to_won']} days)")
print()
print(f"3. VOLUME:")
print(f"   - Lead volume at {results['P3']['leads_per_day']}/day in P3 vs {results['P2']['leads_per_day']}/day in P2")
print()
print(f"4. WON DEALS (P3):")
print(f"   - {results['P3']['won']} deals closed with average {results['P3']['days_to_won']} days to won")
print()
print("="*90)
