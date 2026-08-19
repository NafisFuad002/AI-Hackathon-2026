"""
database.py
------------
এই ফাইলটা SQLite ডেটাবেজের সাথে connection বানায় এবং সব টেবিল (table)
তৈরি করে। অ্যাপ প্রথমবার চালু হলে init_db() ফাংশনটা সব টেবিল বানিয়ে দেয়।

টেবিলগুলো:
1. professionals        -> লগইন করা ইউজার (যারা assessment নেয়)
2. students              -> student basic info
3. assessments           -> প্রতিটা assessment session (একজন student এর জন্য
                            একবার "New Assessment" শুরু করলে একটা row তৈরি হয়)
4. questionnaire_results -> ১১টা প্রশ্নের উত্তর + model output
5. voice_results         -> voice file path + model output
6. handwriting_results   -> handwriting file path + model output (৩য় মডেল)
"""

import sqlite3
import os

# ডেটাবেজ ফাইলটা backend ফোল্ডারের ভেতরেই থাকবে
DB_PATH = os.path.join(os.path.dirname(__file__), "app_database.db")


def get_connection():
    """
    প্রতিটা request এর জন্য একটা নতুন SQLite connection রিটার্ন করে।
    row_factory = sqlite3.Row দেওয়া হয়েছে যাতে আমরা query result কে
    dictionary এর মতো column নাম দিয়ে access করতে পারি (যেমন row["name"])।
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Foreign key constraint enable করা হলো, নাহলে SQLite by default এটা বন্ধ রাখে
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """
    অ্যাপ চালু হওয়ার সময় এই ফাংশন কল হবে (main.py তে)।
    IF NOT EXISTS দেওয়া আছে, তাই বারবার চালালেও পুরনো ডেটা মুছে যাবে না।
    """
    conn = get_connection()
    cur = conn.cursor()

    # ---------------------------------------------------------------
    # 1) PROFESSIONALS TABLE (যারা লগইন করে assessment নেয়)
    # ---------------------------------------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS professionals (
            professional_id     INTEGER PRIMARY KEY AUTOINCREMENT,
            name                 TEXT NOT NULL,
            email                TEXT UNIQUE NOT NULL,
            phone_number         TEXT,
            gender               TEXT,
            nid                  TEXT,
            blood_group          TEXT,
            password_hash        TEXT NOT NULL,   -- plain password কখনো সেভ হবে না
            security_question    TEXT NOT NULL,
            security_answer_hash TEXT NOT NULL,    -- answer ও hash করে রাখা হবে
            created_at           TEXT DEFAULT (datetime('now'))
        )
    """)

    # ---------------------------------------------------------------
    # 🆕 MIGRATION: পুরনো ডেটাবেজে professionals টেবিলে gender/nid/
    # blood_group কলাম নাও থাকতে পারে (CREATE TABLE IF NOT EXISTS পুরনো
    # টেবিল বদলায় না) - তাই ALTER TABLE দিয়ে জোর করে যোগ করার চেষ্টা করা
    # হচ্ছে। কলাম আগে থেকেই থাকলে OperationalError আসবে, সেটা চুপচাপ
    # ignore করে দিচ্ছি।
    # ---------------------------------------------------------------
    for column in ("gender", "nid", "blood_group"):
        try:
            cur.execute(f"ALTER TABLE professionals ADD COLUMN {column} TEXT")
        except sqlite3.OperationalError:
            pass

    # ---------------------------------------------------------------
    # 1.1) LOGIN ATTEMPT TRACKING (security question lockout এর জন্য)
    #      প্রতিটা professional এর জন্য আলাদা row থাকবে
    # ---------------------------------------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS recovery_lockout (
            professional_id   INTEGER PRIMARY KEY,
            wrong_attempts    INTEGER DEFAULT 0,   -- বর্তমান ধারাবাহিক ভুল উত্তরের সংখ্যা
            blocked_until     TEXT,                -- এই সময় পর্যন্ত ব্লক থাকবে (ISO datetime string)
            lockout_stage     INTEGER DEFAULT 0,   -- কততম বার ব্লক হয়েছে (30s->1,1min->2 ...)
            FOREIGN KEY (professional_id) REFERENCES professionals(professional_id)
        )
    """)

    # ---------------------------------------------------------------
    # 2) STUDENTS TABLE
    # ---------------------------------------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS students (
            student_id     TEXT PRIMARY KEY,   -- ইউনিভার্সিটির নিজস্ব Student ID (unique)
            name            TEXT NOT NULL,
            email           TEXT,
            phone_number    TEXT,
            department      TEXT,
            batch           TEXT,
            semester        TEXT,
            section         TEXT,
            blood_group     TEXT,
            date_of_birth   TEXT,
            age             INTEGER,
            gender          TEXT,
            created_at      TEXT DEFAULT (datetime('now'))
        )
    """)

    # ---------------------------------------------------------------
    # 3) ASSESSMENTS TABLE (একটা assessment "সেশন")
    #    প্রতিবার "New Assessment" শুরু করলে একটা নতুন row তৈরি হয়
    # ---------------------------------------------------------------
    # is_finalized: 0 = এখনো এডিট করা যাবে (draft অবস্থা)
    #               1 = "Save Assessment" বাটনে ক্লিক করে ফাইনাল/লক করা হয়ে গেছে,
    #                   আর কোনো questionnaire/voice/handwriting এডিট বা resubmit করা যাবে না
    # 🆕 professional_id এখন nullable (NOT NULL সরানো হলো)। কারণ:
    # admin panel থেকে একটা Professional এর account ডিলিট করার সময় তার
    # নেওয়া assessment গুলো মুছে ফেলা হয় না (student এর data সংরক্ষণের
    # জন্য) - শুধু professional_id = NULL করে দেওয়া হয় (main.py এর
    # api_admin_delete_professional দ্রষ্টব্য)। এটা করতে হলে কলামটা
    # NULL গ্রহণ করতে সক্ষম হতে হবে।
    cur.execute("""
        CREATE TABLE IF NOT EXISTS assessments (
            assessment_id     INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id         TEXT NOT NULL,
            professional_id    INTEGER,
            created_at         TEXT DEFAULT (datetime('now')),
            is_finalized       INTEGER DEFAULT 0,
            FOREIGN KEY (student_id) REFERENCES students(student_id),
            FOREIGN KEY (professional_id) REFERENCES professionals(professional_id)
        )
    """)

    # ---------------------------------------------------------------
    # 🆕 MIGRATION (assessments.professional_id nullable করা) - এটা
    # is_finalized migration এর পরে করা হচ্ছে, দেখো নিচে ⬇️
    # কলাম আগে থেকেই থাকলে SQLite একটা OperationalError দেবে, সেটা
    # চুপচাপ ignore করে দিচ্ছি (মানে "ইতিমধ্যে আছে, সমস্যা নেই")।
    # ---------------------------------------------------------------
    # is_finalized কলামটা এই মাত্র নতুন যোগ হলো কিনা সেটা মনে রাখছি -
    # যদি নতুন যোগ হয় (মানে এটা এমন একটা পুরনো ডেটাবেজ যেখানে আগে এই
    # ফিচারটাই ছিল না), তাহলে নিচে একটা one-time "backfill" চালানো হবে
    # (পুরনো assessment গুলোকে finalized হিসেবে চিহ্নিত করার জন্য)
    is_legacy_database = False
    try:
        cur.execute("ALTER TABLE assessments ADD COLUMN is_finalized INTEGER DEFAULT 0")
        is_legacy_database = True
    except sqlite3.OperationalError:
        pass  # কলাম আগে থেকেই আছে - মানে এটা পুরনো ডেটাবেজ না, normal case

    # ---------------------------------------------------------------
    # 🆕 MIGRATION: পুরনো ডেটাবেজে assessments.professional_id এখনও
    # "NOT NULL" থাকতে পারে (CREATE TABLE IF NOT EXISTS পুরনো টেবিল
    # বদলায় না)। SQLite তে সরাসরি ALTER TABLE দিয়ে একটা কলাম থেকে
    # NOT NULL সরানো যায় না - তাই পুরো টেবিলটা নতুন করে বানিয়ে
    # (rebuild করে) ডেটা কপি করে নেওয়া হচ্ছে। এটা একবারই চলবে, এবং
    # এটা উপরের is_finalized migration এর *পরে* করা হচ্ছে যাতে
    # is_finalized কলাম ততক্ষণে নিশ্চিতভাবে থাকে (নাহলে খুব পুরনো
    # ডেটাবেজে নিচের SELECT এ "no such column" error আসতে পারত)।
    #
    # নিরাপত্তার জন্য: rebuild করার সময় সাময়িকভাবে foreign_keys বন্ধ
    # রাখা হচ্ছে (নাহলে rebuild এর মাঝপথে constraint error আসতে পারে),
    # শেষে আবার চালু করে দেওয়া হচ্ছে। questionnaire_results/
    # voice_results/handwriting_results এর FK assessments(assessment_id)
    # কে নাম দিয়ে refer করে (কোনো internal pointer না), তাই টেবিল
    # rebuild করে আগের নামেই ফিরিয়ে আনলে ওই তিনটা টেবিলের ডেটা/সম্পর্ক
    # অক্ষত থাকে।
    # ---------------------------------------------------------------
    cur.execute("PRAGMA table_info(assessments)")
    professional_id_col = next(
        (c for c in cur.fetchall() if c["name"] == "professional_id"), None
    )
    if professional_id_col is not None and professional_id_col["notnull"] == 1:
        cur.execute("PRAGMA foreign_keys = OFF")
        cur.execute("""
            CREATE TABLE assessments_new (
                assessment_id     INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id         TEXT NOT NULL,
                professional_id    INTEGER,
                created_at         TEXT DEFAULT (datetime('now')),
                is_finalized       INTEGER DEFAULT 0,
                FOREIGN KEY (student_id) REFERENCES students(student_id),
                FOREIGN KEY (professional_id) REFERENCES professionals(professional_id)
            )
        """)
        cur.execute("""
            INSERT INTO assessments_new (assessment_id, student_id, professional_id, created_at, is_finalized)
            SELECT assessment_id, student_id, professional_id, created_at, is_finalized FROM assessments
        """)
        cur.execute("DROP TABLE assessments")
        cur.execute("ALTER TABLE assessments_new RENAME TO assessments")
        cur.execute("PRAGMA foreign_keys = ON")
        print("[database.py] migration: assessments.professional_id কে nullable করা হলো")

    # ---------------------------------------------------------------
    # 4) QUESTIONNAIRE RESULTS (১১টা ফিল্ড + model output)
    # ---------------------------------------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS questionnaire_results (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            assessment_id          INTEGER NOT NULL,
            applicable              INTEGER DEFAULT 1,  -- 0 হলে "not applicable" (এই assessment নেওয়া হয়নি)
            age                     INTEGER,
            gender                  TEXT,
            stress_level            TEXT,
            academic_performance    TEXT,
            health_condition        TEXT,
            relationship_condition  TEXT,
            family_problem          TEXT,
            depression_level        TEXT,
            anxiety_level           TEXT,
            mental_support          TEXT,
            self_harm_history       TEXT,
            model_output            TEXT,   -- মডেলের প্রেডিকশন (একটা word)
            FOREIGN KEY (assessment_id) REFERENCES assessments(assessment_id)
        )
    """)

    # ---------------------------------------------------------------
    # 5) VOICE RESULTS
    # ---------------------------------------------------------------
    # confidence_percent ও risk_level আগে সেভ হতো না (শুধু model_output
    # word হিসেবে সেভ হতো), ফলে assessment একবার Save/লক হয়ে গেলে এই
    # তথ্যগুলো হারিয়ে যেত। এখন এই দুইটা কলাম যোগ করা হলো, যাতে "Save
    # হয়ে যাওয়া" assessment এর read-only view এ পুরো তথ্য (confidence,
    # risk level সহ) দেখানো যায়।
    cur.execute("""
        CREATE TABLE IF NOT EXISTS voice_results (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            assessment_id        INTEGER NOT NULL,
            applicable            INTEGER DEFAULT 1,
            file_path             TEXT,
            model_output          TEXT,
            confidence_percent    REAL,
            risk_level            TEXT,
            FOREIGN KEY (assessment_id) REFERENCES assessments(assessment_id)
        )
    """)

    # MIGRATION: পুরনো ডেটাবেজে voice_results এ এই দুইটা কলাম নাও থাকতে পারে
    try:
        cur.execute("ALTER TABLE voice_results ADD COLUMN confidence_percent REAL")
    except sqlite3.OperationalError:
        pass
    try:
        cur.execute("ALTER TABLE voice_results ADD COLUMN risk_level TEXT")
    except sqlite3.OperationalError:
        pass

    # ---------------------------------------------------------------
    # 6) HANDWRITING RESULTS (৩য় মডেল - input type পরে চূড়ান্ত হবে)
    # ---------------------------------------------------------------
    # voice_results এর মতোই এখানেও confidence_percent/risk_level কলাম
    # যোগ করা হলো (কারণ predict_handwriting() আগে থেকেই এই তথ্য রিটার্ন
    # করে, শুধু আগে ডেটাবেজে সেভ করা হচ্ছিল না)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS handwriting_results (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            assessment_id        INTEGER NOT NULL,
            applicable            INTEGER DEFAULT 1,
            file_path             TEXT,
            model_output          TEXT,
            confidence_percent    REAL,
            risk_level            TEXT,
            FOREIGN KEY (assessment_id) REFERENCES assessments(assessment_id)
        )
    """)

    # MIGRATION: পুরনো ডেটাবেজে handwriting_results এ এই দুইটা কলাম নাও থাকতে পারে
    try:
        cur.execute("ALTER TABLE handwriting_results ADD COLUMN confidence_percent REAL")
    except sqlite3.OperationalError:
        pass
    try:
        cur.execute("ALTER TABLE handwriting_results ADD COLUMN risk_level TEXT")
    except sqlite3.OperationalError:
        pass

    # -------------------------------------------------------------------
    # 🆕 ONE-TIME BACKFILL (শুধু পুরনো ডেটাবেজের জন্য, একবারই চলবে):
    # is_finalized ফিচারটা আগে ছিল না, তাই আগে থেকে যেসব assessment এ
    # ইতিমধ্যে কমপক্ষে একটা প্যানেল (questionnaire/voice/handwriting)
    # সাবমিট করা হয়ে গেছে (applicable = 1), সেগুলোকে এখন "past/সম্পন্ন
    # assessment" হিসেবে ধরে is_finalized = 1 করে লক করে দেওয়া হচ্ছে।
    # যেসব assessment এ এখনো কিছুই সাবমিট হয়নি (সব applicable = 0),
    # সেগুলো এখনো এডিটযোগ্যই থাকবে - সেগুলোতে অ্যাসেসমেন্ট এখনো "চলমান"।
    # -------------------------------------------------------------------
    if is_legacy_database:
        cur.execute("""
            UPDATE assessments
            SET is_finalized = 1
            WHERE assessment_id IN (
                SELECT assessment_id FROM questionnaire_results WHERE applicable = 1
                UNION
                SELECT assessment_id FROM voice_results WHERE applicable = 1
                UNION
                SELECT assessment_id FROM handwriting_results WHERE applicable = 1
            )
        """)
        print("[database.py] পুরনো Assessment গুলো (যেখানে আগে থেকে ফলাফল সাবমিট করা আছে) এখন Save/লক করা হলো")

    conn.commit()
    conn.close()
    print("[database.py] সব টেবিল তৈরি/চেক করা হয়েছে -> app_database.db")


def seed_default_professional():
    """
    অ্যাপ প্রথমবার চালু হলে nafis এর account টা automatically তৈরি করে
    দেয়, যদি আগে থেকে না থেকে থাকে। এতে আলাদা করে sign-up ফর্ম ছাড়াই
    সরাসরি লগইন করা যাবে।
    Login credentials: email = nafis@gmail.com , password = nafis

    নোট: Security question/answer একটা ডিফল্ট মান দিয়ে বসানো হলো
    (Forgot Password ফিচারের জন্য প্রয়োজন)। চাইলে Profile থেকে বা
    সরাসরি ডেটাবেজ থেকে এটা পরে বদলে নিতে পারবে।
    """
    from auth import hash_value  # circular import এড়াতে ফাংশনের ভেতরে import করা হলো

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM professionals WHERE email = ?", ("nafis@gmail.com",))
    existing = cur.fetchone()

    if not existing:
        cur.execute("""
            INSERT INTO professionals
                (name, email, phone_number, password_hash,
                 security_question, security_answer_hash)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            "Nafis",
            "nafis@gmail.com",
            None,
            hash_value("nafis"),
            "What is your favorite color?",
            hash_value("blue"),
        ))
        conn.commit()
        print("[database.py] Professional account তৈরি হয়েছে (nafis@gmail.com / nafis)")

    conn.close()
