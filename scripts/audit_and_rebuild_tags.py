import os
import sys
import shutil
import sqlite3
import argparse
from datetime import datetime

# Add root directory to sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

import utils
import database

def backup_database():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    db_path = database.DB_PATH
    backup_path = os.path.join(database.DATA_DIR, f"jobs_backup_{timestamp}.db")
    shutil.copy2(db_path, backup_path)
    print(f"🔒 Database backup created successfully at: {backup_path}", flush=True)
    return backup_path

def run_audit_and_rebuild(apply_changes=False):
    config = utils.load_config()
    keywords = config.get("keywords", [])
    negative_keywords = config.get("negative_keywords", [])
    evaluator_min_score = config.get("evaluator_min_score", 5)

    conn = database.get_connection()
    c = conn.cursor()
    c.execute("SELECT link, title, description, keywords, negative_keywords, description_tags, neg_description_tags, keyword_score, eval_score, eval_reason FROM jobs")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()

    total_rows = len(rows)
    print(f"\n📊 Auditing {total_rows} jobs in database...", flush=True)
    print(f"   Config has {len(keywords)} positive keywords, {len(negative_keywords)} negative keywords.\n", flush=True)

    changes_count = 0
    pos_title_diff_count = 0
    neg_title_diff_count = 0
    pos_desc_diff_count = 0
    neg_desc_diff_count = 0
    score_diff_count = 0

    removed_false_positives = {}
    removed_neg_title_leaks = 0

    records_to_update = []

    for i, row in enumerate(rows):
        if (i + 1) % 250 == 0 or (i + 1) == total_rows:
            print(f"   ... Processed {i + 1}/{total_rows} jobs", flush=True)
        link = row["link"]
        title = row["title"] or ""
        desc = row["description"] or ""
        
        old_pos_title = row.get("keywords") or ""
        old_neg_title = row.get("negative_keywords") or ""
        old_pos_desc = row.get("description_tags") or ""
        old_neg_desc = row.get("neg_description_tags") or ""
        old_score = row.get("keyword_score") or 0

        # Run token-aware / word-boundary matching
        new_pos_title_list = utils.match_keywords(title, keywords)
        new_neg_title_list = utils.match_keywords(title, negative_keywords)
        new_pos_desc_list = utils.match_keywords(desc, keywords)
        new_neg_desc_list = utils.match_keywords(desc, negative_keywords)

        new_pos_title = ", ".join(new_pos_title_list)
        new_neg_title = ", ".join(new_neg_title_list)
        new_pos_desc = ", ".join(new_pos_desc_list)
        new_neg_desc = ", ".join(new_neg_desc_list)

        new_score = (len(new_pos_title_list) * 2) - (len(new_neg_title_list) * 3) + len(new_pos_desc_list) - len(new_neg_desc_list)

        # Track differences
        has_diff = False
        if old_pos_title != new_pos_title:
            pos_title_diff_count += 1
            has_diff = True
            # Analyze removed false positive tags
            old_set = set([k.strip().lower() for k in old_pos_title.split(",") if k.strip()])
            new_set = set([k.strip().lower() for k in new_pos_title_list])
            removed = old_set - new_set
            for term in removed:
                removed_false_positives[term] = removed_false_positives.get(term, 0) + 1

        if old_neg_title != new_neg_title:
            neg_title_diff_count += 1
            has_diff = True
            if old_neg_title and not new_neg_title:
                removed_neg_title_leaks += 1

        if old_pos_desc != new_pos_desc:
            pos_desc_diff_count += 1
            has_diff = True

        if old_neg_desc != new_neg_desc:
            neg_desc_diff_count += 1
            has_diff = True

        if old_score != new_score:
            score_diff_count += 1
            has_diff = True

        if has_diff:
            changes_count += 1
            records_to_update.append((
                new_pos_title,
                new_neg_title,
                new_pos_desc,
                new_neg_desc,
                new_score,
                link
            ))

    print(f"\n📈 Audit Results Summary:", flush=True)
    print(f"   • Total rows analyzed:               {total_rows}", flush=True)
    print(f"   • Rows with any tag/score change:   {changes_count} ({changes_count/total_rows*100:.1f}%)", flush=True)
    print(f"   • Positive Title tags corrected:    {pos_title_diff_count}", flush=True)
    print(f"   • Negative Title tags corrected:    {neg_title_diff_count} (including {removed_neg_title_leaks} leaked card snippets cleared)", flush=True)
    print(f"   • Positive Description tags cleaned:{pos_desc_diff_count}", flush=True)
    print(f"   • Negative Description tags cleaned:{neg_desc_diff_count}", flush=True)
    print(f"   • Keyword Scores recalibrated:      {score_diff_count}", flush=True)

    if removed_false_positives:
        print(f"\n🔍 Top False Positive Title Tags Eliminated (Previously matched as substrings):", flush=True)
        sorted_fp = sorted(removed_false_positives.items(), key=lambda x: x[1], reverse=True)[:15]
        for term, count in sorted_fp:
            print(f"   - '{term}': removed from {count} titles", flush=True)

    if apply_changes:
        print(f"\n💾 Applying changes to {len(records_to_update)} rows in database...")
        conn = database.get_connection()
        c = conn.cursor()
        c.executemany("""
            UPDATE jobs
            SET keywords = ?,
                negative_keywords = ?,
                description_tags = ?,
                neg_description_tags = ?,
                keyword_score = ?
            WHERE link = ?
        """, records_to_update)
        conn.commit()

        # Update eval_reason threshold placeholders if needed
        c.execute("SELECT link, keyword_score, eval_score, eval_reason FROM jobs")
        all_jobs = [dict(r) for r in c.fetchall()]
        eval_updates = []
        for job in all_jobs:
            if job.get('eval_score') is None or job.get('eval_score') == '':
                curr_reason = job.get('eval_reason') or ''
                score = job.get('keyword_score') or 0
                if score >= evaluator_min_score:
                    if curr_reason.startswith('Below threshold'):
                        eval_updates.append(('', job['link']))
                else:
                    if not curr_reason or curr_reason.startswith('Below threshold'):
                        eval_updates.append((f"Below threshold (kw_score={score})", job['link']))

        if eval_updates:
            c.executemany("UPDATE jobs SET eval_reason = ? WHERE link = ?", eval_updates)
            conn.commit()

        conn.close()
        print(f"✅ Successfully updated {len(records_to_update)} job records and synchronized threshold markers!")
    else:
        print(f"\nℹ️  Dry-run complete. No changes were written to the database. Run with --apply to apply changes.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Audit and rebuild keyword tags and scores.")
    parser.add_argument("--apply", action="store_true", help="Apply the audited tag and score changes to the database.")
    args = parser.parse_args()

    backup_database()
    run_audit_and_rebuild(apply_changes=args.apply)
