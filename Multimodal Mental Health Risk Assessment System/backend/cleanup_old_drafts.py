"""
cleanup_old_drafts.py
-----------------------
🆕 এটা একবার চালানোর (one-time) স্ক্রিপ্ট - এই bug fix আসার আগে যেসব
"খালি" draft assessment (is_finalized=0, তিনটা প্যানেলের একটাও কখনো
applicable=1 হয়নি) ইতিমধ্যে app_database.db তে জমে আছে, সেগুলো একবারে
মুছে ফেলার জন্য।

নতুন করে "New Assessment" শুরু করলে main.py নিজে থেকেই ভবিষ্যতে এই
cleanup করে দেবে (দেখো main.py এর _cleanup_empty_draft_assessments)।
কিন্তু এই bug fix এর আগে যেগুলো জমে গেছে সেগুলো মুছতে এই স্ক্রিপ্টটা
একবার চালাও।

চালানোর নিয়ম (backend ফোল্ডারে গিয়ে, terminal এ):
    python cleanup_old_drafts.py

⚠️ এটা চালানোর আগে app_database.db এর একটা backup (কপি) রেখে দেওয়া
ভালো অভ্যাস, যদিও এই স্ক্রিপ্ট শুধু "সম্পূর্ণ খালি" draft-ই মোছে,
কোনো real assessment data (Save করা বা আংশিক পূরণ করা) স্পর্শ করে না।
"""

import sqlite3
import shutil
from datetime import datetime

DB_PATH = "app_database.db"  # main.py যেভাবে DB ফাইল খুঁজে পায় ঠিক সেভাবেই


def backup_database():
    """
    🛟 Delete করার আগে app_database.db এর একটা টাইমস্ট্যাম্প-সহ কপি
    বানিয়ে রাখে (যেমন app_database.backup_20260819_143000.db)। ভুল কিছু
    হলে এই backup ফাইলটার নাম বদলে (rename করে) app_database.db বানিয়ে
    দিলেই আগের অবস্থায় ফিরে যাওয়া যাবে।
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"app_database.backup_{timestamp}.db"
    shutil.copy2(DB_PATH, backup_path)
    print(f"🛟 Backup রাখা হলো: {backup_path}")
    return backup_path


def main():
    backup_database()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT assessment_id FROM assessments WHERE is_finalized = 0")
    draft_ids = [row["assessment_id"] for row in cur.fetchall()]

    deleted_count = 0
    for aid in draft_ids:
        cur.execute("SELECT applicable FROM questionnaire_results WHERE assessment_id = ?", (aid,))
        q = cur.fetchone()
        cur.execute("SELECT applicable FROM voice_results WHERE assessment_id = ?", (aid,))
        v = cur.fetchone()
        cur.execute("SELECT applicable FROM handwriting_results WHERE assessment_id = ?", (aid,))
        h = cur.fetchone()

        is_completely_empty = (
            (q is None or q["applicable"] == 0)
            and (v is None or v["applicable"] == 0)
            and (h is None or h["applicable"] == 0)
        )

        if is_completely_empty:
            cur.execute("DELETE FROM questionnaire_results WHERE assessment_id = ?", (aid,))
            cur.execute("DELETE FROM voice_results WHERE assessment_id = ?", (aid,))
            cur.execute("DELETE FROM handwriting_results WHERE assessment_id = ?", (aid,))
            cur.execute("DELETE FROM assessments WHERE assessment_id = ?", (aid,))
            deleted_count += 1

    conn.commit()
    conn.close()
    print(f"✅ মোট {deleted_count} টা খালি draft assessment মুছে ফেলা হয়েছে।")


if __name__ == "__main__":
    main()
