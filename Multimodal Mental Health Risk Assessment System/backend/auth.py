"""
auth.py
--------
লগইন, পাসওয়ার্ড হ্যাশিং এবং "Forgot Password -> Security Question ->
Escalating Lockout" এর পুরো লজিক এখানে আছে।

Lockout Rule (তোমার স্পেসিফিকেশন অনুযায়ী):
    - প্রথম ৩টা ভুল উত্তরের পর           -> ৩০ সেকেন্ড ব্লক
    - এরপর আবার ৩টা ভুল উত্তরের পর        -> ১ মিনিট ব্লক
    - এরপর                                -> ২ মিনিট ব্লক
    - এরপর                                -> ৪ মিনিট ব্লক
    - এরপর প্রতিবার                       -> আগের ব্লক টাইমের দ্বিগুণ (exponential)

    আমরা "lockout_stage" নামে একটা কাউন্টার রাখছি যেটা প্রতিবার ৩টা ভুল
    উত্তরের পর ১ করে বাড়ে। lockout_stage থেকে ব্লক-সময় (সেকেন্ডে) বের
    করার সূত্র: 30 * (2 ** (stage - 1))
        stage 1 -> 30 * 2^0 = 30s
        stage 2 -> 30 * 2^1 = 60s  (1 min)
        stage 3 -> 30 * 2^2 = 120s (2 min)
        stage 4 -> 30 * 2^3 = 240s (4 min)   ... ইত্যাদি
"""

import hashlib
from datetime import datetime, timedelta
from database import get_connection

# প্রতি কতবার ভুল উত্তর দিলে একটা নতুন lockout স্টেজ শুরু হবে
WRONG_ATTEMPTS_BEFORE_LOCK = 3


def hash_value(value: str) -> str:
    """
    পাসওয়ার্ড বা security answer সরাসরি ডেটাবেজে সেভ না করে হ্যাশ করে রাখি।
    এটা SHA-256 ব্যবহার করছে। (production এ bcrypt/argon2 বেশি ভালো, কিন্তু
    এখানে সহজ রাখার জন্য SHA-256 ব্যবহার করা হলো)
    """
    return hashlib.sha256(value.strip().lower().encode("utf-8")).hexdigest()


def verify_login(email: str, password: str):
    """
    Email + Password দিয়ে লগইন verify করে।
    সফল হলে professional এর row (dict) রিটার্ন করে, নাহলে None।
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM professionals WHERE email = ?", (email,))
    row = cur.fetchone()
    conn.close()

    if row is None:
        return None

    if row["password_hash"] == hash_value(password):
        return dict(row)
    return None


def get_security_question(email: str):
    """
    Forgot Password ফ্লো এর প্রথম ধাপ: email দিয়ে professional খুঁজে
    তার security question রিটার্ন করে (answer নয়, শুধু question)।
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT professional_id, security_question FROM professionals WHERE email = ?",
        (email,),
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def _get_lockout_row(cur, professional_id):
    cur.execute(
        "SELECT * FROM recovery_lockout WHERE professional_id = ?",
        (professional_id,),
    )
    row = cur.fetchone()
    if row is None:
        # এই professional এর জন্য এখনো কোনো lockout row নেই -> একটা বানিয়ে দিই
        cur.execute(
            "INSERT INTO recovery_lockout (professional_id, wrong_attempts, lockout_stage) VALUES (?, 0, 0)",
            (professional_id,),
        )
        return {"professional_id": professional_id, "wrong_attempts": 0,
                "blocked_until": None, "lockout_stage": 0}
    return dict(row)


def check_lockout_status(professional_id: int):
    """
    এই professional এর security question recovery বর্তমানে ব্লক আছে কিনা
    চেক করে। ব্লক থাকলে (True, remaining_seconds) রিটার্ন করে,
    নাহলে (False, 0)।
    """
    conn = get_connection()
    cur = conn.cursor()
    lockout = _get_lockout_row(cur, professional_id)
    conn.commit()

    if lockout["blocked_until"]:
        blocked_until = datetime.fromisoformat(lockout["blocked_until"])
        now = datetime.now()
        if now < blocked_until:
            remaining = int((blocked_until - now).total_seconds())
            conn.close()
            return True, remaining

    conn.close()
    return False, 0


def verify_security_answer(professional_id: int, answer: str):
    """
    Security answer verify করে। এর সাথে lockout logic ও এখানেই হ্যান্ডেল হয়।

    রিটার্ন করে একটা dict:
        {"success": True}                                -> উত্তর সঠিক
        {"success": False, "blocked": False}              -> উত্তর ভুল, এখনো ব্লক হয়নি
        {"success": False, "blocked": True, "seconds": N} -> উত্তর ভুল এবং এখন ব্লক হয়ে গেছে
    """
    conn = get_connection()
    cur = conn.cursor()

    # প্রথমে দেখে নিই আগে থেকেই ব্লক আছে কিনা
    is_blocked, remaining = check_lockout_status(professional_id)
    if is_blocked:
        conn.close()
        return {"success": False, "blocked": True, "seconds": remaining}

    # আসল professional row থেকে সঠিক answer hash বের করি
    cur.execute(
        "SELECT security_answer_hash FROM professionals WHERE professional_id = ?",
        (professional_id,),
    )
    prof_row = cur.fetchone()
    if prof_row is None:
        conn.close()
        return {"success": False, "blocked": False}

    correct_hash = prof_row["security_answer_hash"]
    given_hash = hash_value(answer)

    lockout = _get_lockout_row(cur, professional_id)

    if given_hash == correct_hash:
        # ✅ উত্তর সঠিক -> সব counter রিসেট করে দিই
        cur.execute("""
            UPDATE recovery_lockout
            SET wrong_attempts = 0, blocked_until = NULL, lockout_stage = 0
            WHERE professional_id = ?
        """, (professional_id,))
        conn.commit()
        conn.close()
        return {"success": True}

    # ❌ উত্তর ভুল -> wrong_attempts বাড়াই
    new_wrong_attempts = lockout["wrong_attempts"] + 1

    if new_wrong_attempts >= WRONG_ATTEMPTS_BEFORE_LOCK:
        # ৩টা ভুল উত্তর হয়ে গেছে -> নতুন lockout stage শুরু হবে
        new_stage = lockout["lockout_stage"] + 1
        block_seconds = 30 * (2 ** (new_stage - 1))  # 30, 60, 120, 240, ...
        blocked_until = datetime.now() + timedelta(seconds=block_seconds)

        cur.execute("""
            UPDATE recovery_lockout
            SET wrong_attempts = 0,
                lockout_stage = ?,
                blocked_until = ?
            WHERE professional_id = ?
        """, (new_stage, blocked_until.isoformat(), professional_id))
        conn.commit()
        conn.close()
        return {"success": False, "blocked": True, "seconds": block_seconds}
    else:
        # এখনো ৩টা হয়নি, শুধু counter বাড়িয়ে রাখি
        cur.execute("""
            UPDATE recovery_lockout SET wrong_attempts = ? WHERE professional_id = ?
        """, (new_wrong_attempts, professional_id))
        conn.commit()
        conn.close()
        return {"success": False, "blocked": False}
