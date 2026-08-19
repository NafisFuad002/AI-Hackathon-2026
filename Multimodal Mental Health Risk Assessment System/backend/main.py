"""
main.py
--------
এটাই অ্যাপের মূল entry point। এখানে সব API route (URL) ডিফাইন করা আছে।
FastAPI দিয়ে backend বানানো হয়েছে, HTML page গুলো Jinja2Templates দিয়ে
serve করা হচ্ছে (../templates ফোল্ডার থেকে), আর CSS/JS static ফাইল
../static ফোল্ডার থেকে serve হচ্ছে।

সার্ভার চালানোর কমান্ড (backend ফোল্ডারের ভেতরে গিয়ে):
    uvicorn main:app --reload
তারপর ব্রাউজারে যাও: http://127.0.0.1:8000
"""

import os
import shutil
import uuid

from fastapi import FastAPI, Request, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

import database
import auth
import ml_models
from schemas import (
    LoginRequest, ForgotPasswordEmailRequest, SecurityAnswerRequest,
    ResetPasswordRequest, NewStudentRequest, QuestionnaireRequest,
    AdminLoginRequest, AdminCreateProfessionalRequest,  # Admin panel এর জন্য
    FinalizeAssessmentRequest,  # 🆕 Save Assessment বাটনের বান্ডেলড payload এর জন্য
)

# ---------------------------------------------------------------------
# App সেটআপ
# ---------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(__file__))  # প্রজেক্টের রুট ফোল্ডার

app = FastAPI(title="Student Mental Health Assessment System")

# session ব্যবহার করছি লগইন অবস্থা মনে রাখার জন্য (cookie-based)
# secret_key প্রোডাকশনে অবশ্যই .env থেকে আনতে হবে, এখানে ডেমোর জন্য সরাসরি লেখা
app.add_middleware(SessionMiddleware, secret_key="CHANGE_THIS_SECRET_KEY_IN_PRODUCTION")

# CSS/JS/uploaded files serve করার জন্য
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

VOICE_UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads", "voice")
HANDWRITING_UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads", "handwriting")


@app.on_event("startup")
def on_startup():
    """
    সার্ভার চালু হওয়ার সাথে সাথে ডেটাবেজ টেবিল তৈরি এবং default professional account বানানো হয়।
    """
    database.init_db()
    database.seed_default_professional()


# ---------------------------------------------------------------------
# একটা ছোট helper: request.session এ professional_id না থাকলে
# লগইন পেজে পাঠিয়ে দেয় (protected route গুলোর জন্য ব্যবহার হবে)
# ---------------------------------------------------------------------
def require_login(request: Request):
    professional_id = request.session.get("professional_id")
    if not professional_id:
        return None
    return professional_id


# ---------------------------------------------------------------------
# Admin এর জন্য আলাদা helper। এটা "professional_id" session key না দেখে
# "is_admin" নামের একটা আলাদা session flag চেক করে - এতে সাধারণ
# professional লগইন দিয়ে কেউ ভুলেও/ইচ্ছাকৃতভাবে admin panel এ ঢুকতে
# পারবে না, আবার admin panel থেকে professional area তেও ঢোকা যাবে না।
# ---------------------------------------------------------------------
def require_admin(request: Request):
    return request.session.get("is_admin", False)


# =======================================================================
# PAGE ROUTES (HTML পেজ দেখানোর জন্য)
# =======================================================================

@app.get("/")
def root(request: Request):
    """রুট URL এ গেলে লগইন থাকলে dashboard এ, নাহলে login page এ পাঠায়।"""
    if require_login(request):
        return RedirectResponse("/dashboard")
    return RedirectResponse("/login")


@app.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html")


@app.get("/dashboard")
def dashboard_page(request: Request):
    professional_id = require_login(request)
    if not professional_id:
        return RedirectResponse("/login")

    conn = database.get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM professionals WHERE professional_id = ?", (professional_id,))
    professional = dict(cur.fetchone())

    # =====================================================================
    # 🆕 DASHBOARD STATS বক্স (৪টা) - Front page এ দেখানোর জন্য ৪টা সংখ্যা
    # বের করা হচ্ছে। এই পুরো ব্লকটা শুধুমাত্র "read" (SELECT) করছে, তাই
    # DB তে কোনো পরিবর্তন হচ্ছে না।
    # =====================================================================

    # --- বক্স ১: মোট কতজন Student এর অন্তত একটা Assessment "Save/Complete"
    #     হয়েছে (draft/অসম্পূর্ণ assessment গোনা হচ্ছে না, শুধু
    #     is_finalized = 1 মানে "Save Assessment" বাটনে ক্লিক করে
    #     সম্পূর্ণ করা assessment) ---
    cur.execute("""
        SELECT COUNT(DISTINCT student_id) AS total
        FROM assessments
        WHERE is_finalized = 1
    """)
    total_students_assessed = cur.fetchone()["total"]

    # --- বক্স ২: মোট কতজন Professional (Doctor) আছে system এ ---
    cur.execute("SELECT COUNT(*) AS total FROM professionals")
    total_professionals = cur.fetchone()["total"]

    # --- বক্স ৪: সব Student মিলিয়ে মোট কতগুলো Assessment "Complete"
    #     (Save) হয়েছে। একজন Student একাধিকবার Assessment দিতে পারে,
    #     তাই এটা COUNT(DISTINCT student_id) না, বরং প্রতিটা finalized
    #     assessment row কে গোনা হচ্ছে ---
    cur.execute("""
        SELECT COUNT(*) AS total
        FROM assessments
        WHERE is_finalized = 1
    """)
    total_assessments_completed = cur.fetchone()["total"]

    # -------------------------------------------------------------------
    # --- বক্স ৩: মোট কতজন Student এখন "Risk এ আছে" ---
    #
    # নিয়ম (sir কে বোঝানোর জন্য): প্রতিটা Student এর সবচেয়ে *সাম্প্রতিক*
    # (last) সম্পূর্ণ (finalized) Assessment টাই দেখা হয় - পুরনো
    # Assessment গুলো ধরা হয় না (কারণ Student এর অবস্থা এখন কেমন সেটাই
    # গুরুত্বপূর্ণ, অতীতে কেমন ছিল সেটা না)।
    #
    # সেই "last assessment" এর ৩টা মডেলের (Questionnaire/Voice/
    # Handwriting) মধ্যে যেকোনো *একটা*-তেও যদি রেজাল্ট "Moderate" বা
    # "High" রিস্ক দেখায়, তাহলে সেই Student কে "risky" ধরা হচ্ছে:
    #
    #   - Questionnaire -> model_output কলামে সরাসরি "Moderate-Risk"
    #                       বা "High-Risk" লেখা থাকে (risk শব্দটা এখানে
    #                       value এর ভেতরেই আছে)
    #   - Voice          -> risk_level কলামে "Moderate" বা "High" থাকলে
    #   - Handwriting     -> risk_level কলামে "Moderate" বা "High" থাকলে
    #
    # "Low" এবং "Unknown" কে risky ধরা হচ্ছে না।
    #
    # 🔧 যদি ভবিষ্যতে rule বদলাতে হয় (যেমন শুধু "High" কে risky ধরতে
    # চাইলে "Moderate" বাদ দিতে হবে), তাহলে নিচের WHERE ক্লজের
    # IN ('Moderate', 'High') / IN ('Moderate-Risk', 'High-Risk')
    # অংশটুকু বদলালেই হবে।
    # -------------------------------------------------------------------
    cur.execute("""
        WITH last_assessments AS (
            -- প্রতিটা Student এর জন্য তার সর্বশেষ finalized assessment_id
            -- বের করা হচ্ছে। assessment_id AUTOINCREMENT (সবসময় বাড়তে
            -- থাকে) বলে MAX(assessment_id) মানেই "সবচেয়ে সাম্প্রতিক"।
            SELECT student_id, MAX(assessment_id) AS last_assessment_id
            FROM assessments
            WHERE is_finalized = 1
            GROUP BY student_id
        )
        SELECT COUNT(*) AS total
        FROM last_assessments la
        LEFT JOIN questionnaire_results q ON q.assessment_id = la.last_assessment_id
        LEFT JOIN voice_results        v ON v.assessment_id = la.last_assessment_id
        LEFT JOIN handwriting_results  h ON h.assessment_id = la.last_assessment_id
        WHERE
            (q.applicable = 1 AND q.model_output IN ('Moderate-Risk', 'High-Risk'))
            OR (v.applicable = 1 AND v.risk_level IN ('Moderate', 'High'))
            OR (h.applicable = 1 AND h.risk_level IN ('Moderate', 'High'))
    """)
    total_students_at_risk = cur.fetchone()["total"]

    conn.close()

    return templates.TemplateResponse(request, "dashboard.html", {
        "professional": professional, "active_page": "dashboard",
        # 🆕 ৪টা বক্সের জন্য stats ডেটা টেমপ্লেটে পাঠানো হচ্ছে
        "total_students_assessed": total_students_assessed,
        "total_professionals": total_professionals,
        "total_students_at_risk": total_students_at_risk,
        "total_assessments_completed": total_assessments_completed,
    })


@app.get("/students")
def students_page(request: Request):
    if not require_login(request):
        return RedirectResponse("/login")
    return templates.TemplateResponse(request, "students.html", {"active_page": "students"})


@app.get("/student/{student_id}")
def student_profile_page(request: Request, student_id: str):
    if not require_login(request):
        return RedirectResponse("/login")

    conn = database.get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM students WHERE student_id = ?", (student_id,))
    student_row = cur.fetchone()
    if student_row is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Student not found")
    student = dict(student_row)

    # =====================================================================
    # 🐛 BUG FIX: "New Assessment" শুরু করার সাথে সাথেই (Existing/New
    # student select করলেই) /api/assessments/start endpoint assessments
    # টেবিলে একটা row বানিয়ে ফেলত (is_finalized=0)। এরপর ইউজার যদি কোনো
    # প্যানেল সাবমিট না করেই Back চেপে বেরিয়ে যেত, তাহলেও সেই "খালি/
    # draft" assessment টা DB তে থেকে যেত এবং এই history লিস্টে দেখা
    # যেত। এই খালি assessment এ ক্লিক করলে assessment.html নিজেই
    # is_finalized=0 দেখে editable (ফাঁকা) ফর্ম দেখাত - যেটাকে ইউজার
    # ভুল করে "নতুন assessment পেজে নিয়ে যাচ্ছে, আগের result দেখাচ্ছে
    # না" বলে মনে করছিল। আসলে ওটা routing bug ছিল না - ওই assessment এ
    # আগে থেকে কোনো result-ই সেভ হয়নি (কারণ Save করাই হয়নি)।
    #
    # ✅ FIX: History তে এখন থেকে শুধু is_finalized = 1 (অর্থাৎ "Save
    # Assessment" বাটনে ক্লিক করে সম্পূর্ণ করা) assessment গুলোই
    # দেখানো হবে। Draft/অসম্পূর্ণ assessment গুলো এখানে আর দেখাবে না,
    # আর সেগুলো নিচের /api/assessments/start এ (আরেকটা fix এ) auto
    # delete হয়ে যাবে যদি সেগুলো একদমই খালি থাকে।
    #
    # 🆕 NEW FEATURE: এখন প্রতিটা assessment এর সাথে questionnaire/
    # voice/handwriting - তিনটা result table কে LEFT JOIN করে একসাথে
    # নিয়ে আসা হচ্ছে, যাতে student_profile.html এ প্রতিটা row এ তিনটা
    # মডেলের ফলাফল (অথবা "নেওয়া হয়নি") একসাথে টেবিলে দেখানো যায়,
    # আলাদা করে প্রতিটা assessment পেজে না গিয়েই।
    # =====================================================================
    cur.execute("""
        SELECT
            a.assessment_id,
            a.created_at,

            -- 📝 Questionnaire summary
            q.applicable AS questionnaire_applicable,
            q.model_output AS questionnaire_output,

            -- 🎙️ Voice summary
            v.applicable AS voice_applicable,
            v.model_output AS voice_output,
            v.risk_level AS voice_risk,

            -- ✍️ Handwriting summary
            h.applicable AS handwriting_applicable,
            h.model_output AS handwriting_output,
            h.risk_level AS handwriting_risk

        FROM assessments a
        LEFT JOIN questionnaire_results q ON q.assessment_id = a.assessment_id
        LEFT JOIN voice_results v ON v.assessment_id = a.assessment_id
        LEFT JOIN handwriting_results h ON h.assessment_id = a.assessment_id
        WHERE a.student_id = ? AND a.is_finalized = 1
        ORDER BY a.created_at DESC
    """, (student_id,))
    assessments = [dict(row) for row in cur.fetchall()]
    conn.close()

    return templates.TemplateResponse(request, "student_profile.html", {
        "student": student, "assessments": assessments, "active_page": "students",
    })


@app.get("/profile")
def profile_page(request: Request):
    professional_id = require_login(request)
    if not professional_id:
        return RedirectResponse("/login")

    conn = database.get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT professional_id, name, email, phone_number, gender, nid, blood_group, created_at
        FROM professionals WHERE professional_id = ?
    """, (professional_id,))  # লক্ষ্য করো: password/security fields select করা হয়নি
    professional = dict(cur.fetchone())
    conn.close()

    return templates.TemplateResponse(request, "profile.html", {
        "professional": professional, "active_page": "profile",
    })


@app.get("/new-assessment")
def new_assessment_page(request: Request):
    if not require_login(request):
        return RedirectResponse("/login")
    return templates.TemplateResponse(request, "new_assessment.html", {"active_page": "dashboard"})


@app.get("/assessment/{assessment_id}")
def assessment_page(request: Request, assessment_id: int):
    if not require_login(request):
        return RedirectResponse("/login")

    conn = database.get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT assessments.*, students.name as student_name
        FROM assessments JOIN students ON assessments.student_id = students.student_id
        WHERE assessment_id = ?
    """, (assessment_id,))
    row = cur.fetchone()
    if row is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Assessment not found")
    assessment = dict(row)

    # তিনটা result টেবিল থেকে ডেটা টেনে আনা হচ্ছে। assessment.is_finalized
    # সত্যি (True) হলে টেমপ্লেট এই তথ্যগুলো দিয়ে একটা read-only/সংক্ষিপ্ত
    # টেবিল ভিউ দেখাবে (এডিট করার কোনো ফর্ম দেখাবে না)।
    cur.execute("SELECT * FROM questionnaire_results WHERE assessment_id = ?", (assessment_id,))
    q_row = cur.fetchone()
    cur.execute("SELECT * FROM voice_results WHERE assessment_id = ?", (assessment_id,))
    v_row = cur.fetchone()
    cur.execute("SELECT * FROM handwriting_results WHERE assessment_id = ?", (assessment_id,))
    h_row = cur.fetchone()
    conn.close()

    return templates.TemplateResponse(request, "assessment.html", {
        "assessment": assessment,
        "active_page": "dashboard",
        "questionnaire_result": dict(q_row) if q_row else None,
        "voice_result": dict(v_row) if v_row else None,
        "handwriting_result": dict(h_row) if h_row else None,
    })


@app.get("/logout")
def logout(request: Request):
    request.session.clear()  # সব session data মুছে দিলেই logout হয়ে যায়
    return RedirectResponse("/login")


# =======================================================================
# ADMIN PANEL - PAGE ROUTES
# -----------------------------------------------------------------------
# এটা professionals (যারা assessment নেয়) দের লগইন থেকে সম্পূর্ণ আলাদা।
# id: admin, password: admin (হার্ডকোডেড, api_admin_login() এ চেক হয়)।
# এখান থেকে Professional account তৈরি এবং ডিলিট করা যাবে।
# =======================================================================

@app.get("/admin/login")
def admin_login_page(request: Request):
    # আগে থেকেই admin হিসেবে লগইন করা থাকলে সরাসরি dashboard এ পাঠিয়ে দিই
    if require_admin(request):
        return RedirectResponse("/admin")
    return templates.TemplateResponse(request, "admin_login.html")


@app.get("/admin")
def admin_dashboard_page(request: Request):
    if not require_admin(request):
        return RedirectResponse("/admin/login")
    return templates.TemplateResponse(request, "admin.html")


@app.get("/admin/logout")
def admin_logout(request: Request):
    # পুরো session clear করে দিচ্ছি (শুধু is_admin flag মুছলেও চলত,
    # কিন্তু পুরোপুরি ক্লিয়ার করাই বেশি নিরাপদ)
    request.session.clear()
    return RedirectResponse("/admin/login")


# =======================================================================
# API ROUTES - LOGIN / AUTH
# =======================================================================

@app.post("/api/login")
def api_login(data: LoginRequest, request: Request):
    professional = auth.verify_login(data.email, data.password)
    if professional is None:
        return JSONResponse({"success": False, "message": "ভুল Email অথবা Password"}, status_code=401)

    request.session["professional_id"] = professional["professional_id"]
    return {"success": True, "redirect": "/dashboard"}


@app.post("/api/forgot-password/get-question")
def api_get_security_question(data: ForgotPasswordEmailRequest):
    result = auth.get_security_question(data.email)
    if result is None:
        return JSONResponse({"success": False, "message": "এই Email দিয়ে কোনো Account পাওয়া যায়নি"}, status_code=404)

    # লকআউট এ আছে কিনা আগেই চেক করে জানিয়ে দিই
    is_blocked, remaining = auth.check_lockout_status(result["professional_id"])
    return {
        "success": True,
        "professional_id": result["professional_id"],
        "security_question": result["security_question"],
        "blocked": is_blocked,
        "blocked_seconds": remaining,
    }


@app.post("/api/forgot-password/verify-answer")
def api_verify_security_answer(data: SecurityAnswerRequest):
    result = auth.verify_security_answer(data.professional_id, data.answer)
    return result


@app.post("/api/forgot-password/reset")
def api_reset_password(data: ResetPasswordRequest):
    """
    Security answer সঠিক দেওয়ার পরের ধাপ - নতুন পাসওয়ার্ড সেট করা।
    (Frontend থেকে নিশ্চিত করতে হবে যে verify-answer আগেই success হয়েছে)
    """
    conn = database.get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE professionals SET password_hash = ? WHERE professional_id = ?",
        (auth.hash_value(data.new_password), data.professional_id),
    )
    conn.commit()
    conn.close()
    return {"success": True, "message": "Password সফলভাবে পরিবর্তন হয়েছে"}


# =======================================================================
# API ROUTES - STUDENTS
# =======================================================================

@app.get("/api/students")
def api_list_students(department: str = None, semester: str = None,
                       section: str = None, batch: str = None):
    """
    Students পেজের তালিকা + filter এর জন্য। যেসব filter parameter দেওয়া
    হয়েছে (None নয়) সেগুলো দিয়ে query তে WHERE condition যোগ হয়।
    """
    conn = database.get_connection()
    cur = conn.cursor()

    query = "SELECT student_id, name, department, semester, section, batch FROM students WHERE 1=1"
    params = []

    if department:
        query += " AND department = ?"
        params.append(department)
    if semester:
        query += " AND semester = ?"
        params.append(semester)
    if section:
        query += " AND section = ?"
        params.append(section)
    if batch:
        query += " AND batch = ?"
        params.append(batch)

    cur.execute(query, params)
    students = [dict(row) for row in cur.fetchall()]
    conn.close()
    return {"students": students}


@app.get("/api/students/search/{student_id}")
def api_search_student(student_id: str):
    """Dashboard এর search box এবং New Assessment > Existing Student এ ব্যবহৃত হয়।"""
    conn = database.get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM students WHERE student_id = ?", (student_id,))
    row = cur.fetchone()
    conn.close()

    if row is None:
        return JSONResponse({"found": False}, status_code=404)
    return {"found": True, "student": dict(row)}


@app.post("/api/students")
def api_create_student(data: NewStudentRequest):
    """New Student ফর্ম সাবমিট হলে student কে ডেটাবেজে সেভ করে।"""
    conn = database.get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO students
                (student_id, name, email, phone_number, department, batch,
                 semester, section, blood_group, date_of_birth, age, gender)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.student_id, data.name, data.email, data.phone_number,
            data.department, data.batch, data.semester, data.section,
            data.blood_group, data.date_of_birth, data.age, data.gender,
        ))
        conn.commit()
    except Exception as e:
        conn.close()
        # সাধারণত duplicate student_id দিলে এখানে error আসবে
        return JSONResponse({"success": False, "message": str(e)}, status_code=400)
    conn.close()
    return {"success": True, "student_id": data.student_id}


# =======================================================================
# ADMIN PANEL - API ROUTES
# =======================================================================

@app.post("/api/admin/login")
def api_admin_login(data: AdminLoginRequest, request: Request):
    """
    Admin login - স্পেসিফিকেশন অনুযায়ী id/password হার্ডকোডেড: admin/admin।
    এটা professionals টেবিলের সাথে কোনোভাবেই যুক্ত না।

    ⚠️ নোট: এটা demo/academic project এর জন্য সহজ রাখা হলো। আসল
    production এ এই credential .env/environment variable এ রাখা উচিত,
    আর সরাসরি plain-text compare না করে hash করে রাখা/চেক করা উচিত।
    """
    if data.username == "admin" and data.password == "admin":
        request.session["is_admin"] = True
        return {"success": True, "redirect": "/admin"}
    return JSONResponse({"success": False, "message": "ভুল Admin ID অথবা Password"}, status_code=401)


@app.get("/api/admin/professionals")
def api_admin_list_professionals(request: Request):
    """Admin dashboard এ সব Professional এর তালিকা (সব ডিটেইলসহ) দেখানোর জন্য।"""
    if not require_admin(request):
        raise HTTPException(status_code=401, detail="Admin login required")

    conn = database.get_connection()
    cur = conn.cursor()
    # password_hash/security_answer_hash select করা হচ্ছে না - নিরাপত্তার জন্য
    # 🆕 gender/nid/blood_group ও এখন select করা হচ্ছে, যাতে admin dashboard
    # এর টেবিলে প্রতিটা Professional এর সব তথ্য একসাথে দেখা যায়
    cur.execute("""
        SELECT professional_id, name, email, phone_number, gender, nid, blood_group, created_at
        FROM professionals ORDER BY professional_id
    """)
    professionals = [dict(row) for row in cur.fetchall()]
    conn.close()
    return {"professionals": professionals}


@app.post("/api/admin/professionals")
def api_admin_create_professional(data: AdminCreateProfessionalRequest, request: Request):
    """Admin panel থেকে নতুন Professional (assessment নেওয়ার একাউন্ট) তৈরি করে।"""
    if not require_admin(request):
        raise HTTPException(status_code=401, detail="Admin login required")

    conn = database.get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO professionals
                (name, email, phone_number, gender, nid, blood_group,
                 password_hash, security_question, security_answer_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.name, data.email, data.phone_number,
            data.gender, data.nid, data.blood_group,
            auth.hash_value(data.password),
            data.security_question,
            auth.hash_value(data.security_answer),
        ))
        conn.commit()
    except Exception:
        conn.close()
        # সাধারণত duplicate email দিলে এখানে error আসবে (email UNIQUE constraint)
        return JSONResponse(
            {"success": False, "message": "তৈরি করা যায়নি - সম্ভবত এই Email দিয়ে আগে থেকেই একটা Professional account আছে।"},
            status_code=400,
        )
    conn.close()
    return {"success": True}


@app.delete("/api/admin/professionals/{professional_id}")
def api_admin_delete_professional(professional_id: int, request: Request):
    """
    Admin panel থেকে একটা Professional account ডিলিট করে।

    🐛 BUG FIX: আগে এই endpoint শুধুমাত্র recovery_lockout row মুছে
    সরাসরি DELETE FROM professionals চালাত। কিন্তু assessments টেবিলে
    professional_id ছিল NOT NULL + FOREIGN KEY, তাই যে Professional
    আগে কোনো assessment নিয়েছে, তাকে ডিলিট করতে গেলেই SQLite এর FK
    constraint এ আটকে যেত এবং "ডিলিট করা যায়নি" error দেখাত - ইউজারের
    রিপোর্ট করা bug এটাই ছিল।

    ✅ FIX: এখন থেকে বোঝা যাচ্ছে - assessment টা student ও institution
    এর data, Professional চলে গেলেও (চাকরি ছেড়ে দিলে) সেটা মুছে ফেলা
    ঠিক না, শুধু "কে নিয়েছিল" এই তথ্যটা হারিয়ে যাওয়াই স্বাভাবিক। তাই
    এখন প্রথমে সেই Professional এর নেওয়া সব assessment এ
    professional_id = NULL বসিয়ে দেওয়া হচ্ছে (assessments.professional_id
    এখন nullable - দেখো database.py এর migration), তারপর professional
    row টা ডিলিট করা হচ্ছে। এতে assessment data/history অক্ষত থাকে,
    আর Professional delete করা সবসময় সফল হবে (আলাদা করে try/except
    দিয়ে "assessment আছে" এই বিশেষ কারণে আটকানোর দরকার নেই আর)।
    """
    if not require_admin(request):
        raise HTTPException(status_code=401, detail="Admin login required")

    conn = database.get_connection()
    cur = conn.cursor()

    cur.execute("SELECT professional_id FROM professionals WHERE professional_id = ?", (professional_id,))
    if cur.fetchone() is None:
        conn.close()
        return JSONResponse({"success": False, "message": "এই Professional পাওয়া যায়নি।"}, status_code=404)

    try:
        # এই professional এর নেওয়া assessment গুলো থেকে শুধু "কে নিয়েছিল"
        # এই সম্পর্কটা মুছে দেওয়া হচ্ছে - assessment/result data অক্ষত থাকছে
        cur.execute("UPDATE assessments SET professional_id = NULL WHERE professional_id = ?", (professional_id,))

        # recovery_lockout এ এই professional এর row থাকলে সেটা মুছে দেওয়া
        # হচ্ছে (এটা সত্যিকারের "child" ডেটা, কোনো ভাবেই রাখার দরকার নেই)
        cur.execute("DELETE FROM recovery_lockout WHERE professional_id = ?", (professional_id,))

        cur.execute("DELETE FROM professionals WHERE professional_id = ?", (professional_id,))
        conn.commit()
    except Exception:
        conn.close()
        return JSONResponse(
            {"success": False, "message": "ডিলিট করার সময় একটা সমস্যা হয়েছে, আবার চেষ্টা করো।"},
            status_code=500,
        )
    conn.close()
    return {"success": True}


# =======================================================================
# 🆕 ADMIN PANEL - MANAGE ALL STUDENTS
# ---------------------------------------------------------------------
# Admin কে সার্চ ছাড়াই সব student এর তালিকা এবং তাদের basic তথ্য দেখার
# সুযোগ দেওয়া হচ্ছে, এবং প্রয়োজনে একজন student কে সম্পূর্ণভাবে ডিলিট
# করার সুযোগ (তার সব assessment ও ফলাফলসহ, কারণ assessment টা সরাসরি
# ওই student এর data - student ডিলিট হলে সেটা রাখার কোনো মানে নেই,
# এটা professional_id এর সাথে ভিন্ন - সেখানে শুধু "কে নিয়েছিল" এই
# তথ্যটা হারায়, এখানে পুরো assessment টাই আর প্রাসঙ্গিক থাকে না)।
# =======================================================================

@app.get("/api/admin/students")
def api_admin_list_students(request: Request):
    """Admin dashboard এ সব student এর তালিকা (সার্চ ছাড়াই) দেখানোর জন্য।"""
    if not require_admin(request):
        raise HTTPException(status_code=401, detail="Admin login required")

    conn = database.get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT student_id, name, email, phone_number, department, batch, semester, section
        FROM students ORDER BY student_id
    """)
    students = [dict(row) for row in cur.fetchall()]
    conn.close()
    return {"success": True, "students": students}


@app.delete("/api/admin/students/{student_id}")
def api_admin_delete_student(student_id: str, request: Request):
    """
    Admin panel থেকে একটা student কে সম্পূর্ণভাবে ডিলিট করে - তার সব
    assessment এবং সেই assessment গুলোর questionnaire/voice/handwriting
    result সহ (উপরের professional delete থেকে ভিন্ন - এখানে child ডেটা
    NULL করে রাখা হয় না, পুরোটাই মুছে ফেলা হয়, কারণ assessment টা এই
    student ছাড়া অর্থহীন)।
    """
    if not require_admin(request):
        raise HTTPException(status_code=401, detail="Admin login required")

    conn = database.get_connection()
    cur = conn.cursor()

    cur.execute("SELECT student_id FROM students WHERE student_id = ?", (student_id,))
    if cur.fetchone() is None:
        conn.close()
        return JSONResponse({"success": False, "message": "এই Student পাওয়া যায়নি।"}, status_code=404)

    try:
        # এই student এর সব assessment_id বের করে নিচ্ছি, যাতে সেগুলোর
        # voice/handwriting আপলোড করা ফাইলও ডিস্ক থেকে মুছে ফেলা যায়
        cur.execute("SELECT assessment_id FROM assessments WHERE student_id = ?", (student_id,))
        assessment_ids = [row["assessment_id"] for row in cur.fetchall()]

        file_paths = []
        for aid in assessment_ids:
            for table in ("voice_results", "handwriting_results"):
                cur.execute(f"SELECT file_path FROM {table} WHERE assessment_id = ?", (aid,))
                row = cur.fetchone()
                if row and row["file_path"]:
                    file_paths.append(row["file_path"])

        cur.execute("""
            DELETE FROM questionnaire_results WHERE assessment_id IN
                (SELECT assessment_id FROM assessments WHERE student_id = ?)
        """, (student_id,))
        cur.execute("""
            DELETE FROM voice_results WHERE assessment_id IN
                (SELECT assessment_id FROM assessments WHERE student_id = ?)
        """, (student_id,))
        cur.execute("""
            DELETE FROM handwriting_results WHERE assessment_id IN
                (SELECT assessment_id FROM assessments WHERE student_id = ?)
        """, (student_id,))
        cur.execute("DELETE FROM assessments WHERE student_id = ?", (student_id,))
        cur.execute("DELETE FROM students WHERE student_id = ?", (student_id,))
        conn.commit()
    except Exception:
        conn.close()
        return JSONResponse(
            {"success": False, "message": "ডিলিট করার সময় একটা সমস্যা হয়েছে, আবার চেষ্টা করো।"},
            status_code=500,
        )
    conn.close()

    for path in file_paths:
        try:
            if os.path.isfile(path):
                os.remove(path)
        except OSError:
            pass

    return {"success": True}


# =======================================================================
# 🆕 ADMIN PANEL - MANAGE STUDENT ASSESSMENTS
# ---------------------------------------------------------------------
# Admin কে এখন কোনো নির্দিষ্ট student এর সব সম্পন্ন (Save করা) assessment
# দেখার এবং প্রয়োজনে সেখান থেকে যেকোনো একটা assessment ডিলিট করে দেওয়ার
# সুযোগ দেওয়া হচ্ছে - যেমন ভুল করে সাবমিট হয়ে যাওয়া বা টেস্ট ডেটা মুছে
# ফেলার জন্য।
# =======================================================================

@app.get("/api/admin/students/{student_id}/assessments")
def api_admin_list_student_assessments(student_id: str, request: Request):
    """
    Admin panel এ কোনো student এর সব finalized (Save করা) assessment এর
    তালিকা - তিনটা মডেলের ফলাফলসহ - দেখানোর জন্য। student_profile_page
    এর মতোই query, কিন্তু এটা admin session দিয়ে guarded এবং ডিলিট
    বাটনের জন্য দরকারি assessment_id ও এখানেই থাকছে।
    """
    if not require_admin(request):
        raise HTTPException(status_code=401, detail="Admin login required")

    conn = database.get_connection()
    cur = conn.cursor()

    cur.execute("SELECT student_id, name FROM students WHERE student_id = ?", (student_id,))
    student_row = cur.fetchone()
    if student_row is None:
        conn.close()
        return JSONResponse({"success": False, "message": "এই Student ID দিয়ে কোনো Student পাওয়া যায়নি।"}, status_code=404)

    cur.execute("""
        SELECT
            a.assessment_id,
            a.created_at,
            q.applicable AS questionnaire_applicable,
            q.model_output AS questionnaire_output,
            v.applicable AS voice_applicable,
            v.model_output AS voice_output,
            v.risk_level AS voice_risk,
            h.applicable AS handwriting_applicable,
            h.model_output AS handwriting_output,
            h.risk_level AS handwriting_risk
        FROM assessments a
        LEFT JOIN questionnaire_results q ON q.assessment_id = a.assessment_id
        LEFT JOIN voice_results v ON v.assessment_id = a.assessment_id
        LEFT JOIN handwriting_results h ON h.assessment_id = a.assessment_id
        WHERE a.student_id = ? AND a.is_finalized = 1
        ORDER BY a.created_at DESC
    """, (student_id,))
    assessments = [dict(row) for row in cur.fetchall()]
    conn.close()

    return {"success": True, "student": dict(student_row), "assessments": assessments}


@app.delete("/api/admin/assessments/{assessment_id}")
def api_admin_delete_assessment(assessment_id: int, request: Request):
    """
    Admin panel থেকে একটা নির্দিষ্ট assessment (এর তিনটা result row সহ)
    সম্পূর্ণভাবে ডিলিট করে দেয়। voice/handwriting এর আপলোড করা ফাইল
    ডিস্কে থাকলে সেগুলোও মুছে ফেলার চেষ্টা করা হয়, যাতে orphan ফাইল
    (এমন ফাইল যেটার আর কোনো DB record নেই) জমে না থাকে।
    """
    if not require_admin(request):
        raise HTTPException(status_code=401, detail="Admin login required")

    conn = database.get_connection()
    cur = conn.cursor()

    cur.execute("SELECT assessment_id FROM assessments WHERE assessment_id = ?", (assessment_id,))
    if cur.fetchone() is None:
        conn.close()
        return JSONResponse({"success": False, "message": "এই Assessment পাওয়া যায়নি।"}, status_code=404)

    # ডিলিট করার আগে voice/handwriting এর file_path গুলো বের করে রাখছি,
    # DB row মোছার পরে ওই path গুলো দিয়ে ফাইলও মোছার চেষ্টা করা হবে
    file_paths = []
    for table in ("voice_results", "handwriting_results"):
        cur.execute(f"SELECT file_path FROM {table} WHERE assessment_id = ?", (assessment_id,))
        row = cur.fetchone()
        if row and row["file_path"]:
            file_paths.append(row["file_path"])

    cur.execute("DELETE FROM questionnaire_results WHERE assessment_id = ?", (assessment_id,))
    cur.execute("DELETE FROM voice_results WHERE assessment_id = ?", (assessment_id,))
    cur.execute("DELETE FROM handwriting_results WHERE assessment_id = ?", (assessment_id,))
    cur.execute("DELETE FROM assessments WHERE assessment_id = ?", (assessment_id,))
    conn.commit()
    conn.close()

    # DB থেকে সফলভাবে ডিলিট হওয়ার পরই ফাইল মোছার চেষ্টা করা হচ্ছে -
    # ফাইল মুছতে ব্যর্থ হলেও (যেমন আগে থেকেই না থাকলে) পুরো request
    # fail করানো হচ্ছে না, কারণ DB record মুছে যাওয়াটাই বেশি গুরুত্বপূর্ণ
    for path in file_paths:
        try:
            if os.path.isfile(path):
                os.remove(path)
        except OSError:
            pass

    return {"success": True}
# =======================================================================

@app.post("/api/assessments/start")
def api_start_assessment(student_id: str = Form(...), request: Request = None):
    """
    নতুন assessment session শুরু করে (assessments টেবিলে একটা row বানায়)
    এবং তিনটা result table (questionnaire/voice/handwriting) এ খালি
    "not applicable" row বসিয়ে রাখে, পরে যেটা নেওয়া হবে সেটা আপডেট হবে।
    """
    professional_id = request.session.get("professional_id")
    if not professional_id:
        raise HTTPException(status_code=401, detail="Login required")

    conn = database.get_connection()
    cur = conn.cursor()

    # =====================================================================
    # 🐛 BUG FIX (cleanup): আগে এই endpoint কল হলেই সাথে সাথে assessments
    # টেবিলে একটা row তৈরি হয়ে যেত, ইউজার একটাও প্যানেল পূরণ করার আগেই।
    # ইউজার যদি "New Assessment" এ ঢুকে কিছু না করেই Back চেপে বেরিয়ে
    # যেত (বা ব্রাউজার ট্যাব বন্ধ করে দিত), তাহলে সেই "খালি" assessment
    # row টা is_finalized=0 অবস্থায় DB তে চিরকালের জন্য থেকে যেত এবং
    # student profile এর history তে দেখা যেত।
    #
    # ✅ FIX: এই একই professional এর আগের সব draft (is_finalized=0)
    # assessment চেক করে, যেগুলোতে তিনটা প্যানেলের একটাও (questionnaire/
    # voice/handwriting) কখনো applicable=1 হয়নি (অর্থাৎ পুরোপুরি খালি,
    # কোনোদিন Submit/Predict ও করা হয়নি) - সেগুলোকে DB থেকে মুছে ফেলা
    # হচ্ছে নতুন assessment শুরু করার ঠিক আগে।
    #
    # ⚠️ Note: শুধু "একদম খালি" (কোনো প্যানেল একবারও applicable=1 হয়নি)
    # draft-ই মোছা হচ্ছে - কোনো প্যানেল আংশিক পূরণ/predict করা থাকলে সেটা
    # মোছা হয় না, কারণ ইউজার হয়তো পরে Save করে ফিরে আসতে পারে। এটা student
    # profile এ ইতিমধ্যেই দেখাচ্ছি না (is_finalized=1 filter করা আছে),
    # শুধু DB clean রাখার জন্য এই cleanup যোগ করা হলো।
    # =====================================================================
    _cleanup_empty_draft_assessments(cur, professional_id)

    cur.execute(
        "INSERT INTO assessments (student_id, professional_id) VALUES (?, ?)",
        (student_id, professional_id),
    )
    assessment_id = cur.lastrowid

    # তিনটা টেবিলেই "applicable = 0" (not applicable) দিয়ে ডিফল্ট row রাখা হচ্ছে।
    # যে assessment গুলো আসলে নেওয়া হবে, সেগুলো পরে আলাদা API কল দিয়ে আপডেট হবে।
    cur.execute("INSERT INTO questionnaire_results (assessment_id, applicable) VALUES (?, 0)", (assessment_id,))
    cur.execute("INSERT INTO voice_results (assessment_id, applicable) VALUES (?, 0)", (assessment_id,))
    cur.execute("INSERT INTO handwriting_results (assessment_id, applicable) VALUES (?, 0)", (assessment_id,))

    conn.commit()
    conn.close()
    return {"success": True, "assessment_id": assessment_id}


def _cleanup_empty_draft_assessments(cur, professional_id: int):
    """
    🆕 এই professional এর নামে থাকা draft (is_finalized=0) assessment
    গুলোর মধ্যে যেগুলো সম্পূর্ণ খালি (questionnaire/voice/handwriting -
    তিনটার একটাও কখনো applicable=1 হয়নি) সেগুলো খুঁজে বের করে DB থেকে
    মুছে দেয় (নিজের child result rows সহ, তারপর assessments row)।

    এটা কমিট করে না - কলিং ফাংশন (api_start_assessment) নিজের ইনসার্টের
    সাথে একসাথেই commit করে, যাতে পুরো অপারেশনটা একটা atomic ইউনিট থাকে।
    """
    cur.execute(
        "SELECT assessment_id FROM assessments WHERE professional_id = ? AND is_finalized = 0",
        (professional_id,),
    )
    draft_ids = [row["assessment_id"] for row in cur.fetchall()]

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


# -----------------------------------------------------------------------
# ছোট্ট helper: assessment_id দিয়ে is_finalized (Save/লক অবস্থা) চেক করে।
# পাওয়া না গেলে None, পাওয়া গেলে 0/1 রিটার্ন করে। questionnaire/voice/
# handwriting - এই তিনটা submit endpoint-ই এই ফাংশন ব্যবহার করে, যাতে
# একবার Save হয়ে যাওয়া assessment এ আর কেউ (ভুলে বা ইচ্ছাকৃতভাবে) নতুন
# করে ডেটা বসাতে/এডিট করতে না পারে।
# -----------------------------------------------------------------------
def _get_is_finalized(cur, assessment_id: int):
    cur.execute("SELECT is_finalized FROM assessments WHERE assessment_id = ?", (assessment_id,))
    row = cur.fetchone()
    if row is None:
        return None
    return row["is_finalized"]


@app.post("/api/assessments/{assessment_id}/finalize")
def api_finalize_assessment(assessment_id: int, data: FinalizeAssessmentRequest, request: Request):
    """
    🔄 বদলে গেছে: এখন এটাই একমাত্র জায়গা যেখানে questionnaire/voice/
    handwriting এর ফলাফল আসলে ডেটাবেজে লেখা হয়। "Save Assessment"
    বাটনে ক্লিক করলে assessment.js যা যা প্যানেল সাবমিট করা হয়েছিল
    (prediction থেকে পাওয়া ফলাফলগুলো) সেগুলো এই endpoint এ একসাথে
    বান্ডেল করে পাঠায় - data.questionnaire / data.voice /
    data.handwriting এর মধ্যে যেগুলো None না, শুধু সেগুলোই ডেটাবেজে
    লেখা হয় (applicable=1 সহ)। যেগুলো None (কখনো সাবমিট করা হয়নি),
    সেগুলো আগের মতোই applicable=0 থেকে যায়।

    সব লেখা শেষে assessments.is_finalized = 1 করে দেওয়া হয় - এরপর
    থেকে আর কোনো প্যানেল resubmit/এডিট করা যাবে না (questionnaire/
    voice/handwriting endpoint গুলোর is_finalized চেক এটা আটকায়)।
    """
    if not require_login(request):
        raise HTTPException(status_code=401, detail="Login required")

    conn = database.get_connection()
    cur = conn.cursor()

    current_status = _get_is_finalized(cur, assessment_id)
    if current_status is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Assessment not found")

    if current_status == 1:
        conn.close()
        return JSONResponse(
            {"success": False, "message": "এই Assessment আগেই Save করা হয়ে গেছে।"},
            status_code=400,
        )

    # --- Questionnaire ফলাফল লেখা হচ্ছে (যদি সাবমিট করা হয়ে থাকে) ---
    if data.questionnaire is not None:
        q = data.questionnaire
        cur.execute("""
            UPDATE questionnaire_results
            SET applicable = 1, age = ?, gender = ?, stress_level = ?,
                academic_performance = ?, health_condition = ?,
                relationship_condition = ?, family_problem = ?,
                depression_level = ?, anxiety_level = ?, mental_support = ?,
                self_harm_history = ?, model_output = ?
            WHERE assessment_id = ?
        """, (
            q.age, q.gender, q.stress_level, q.academic_performance,
            q.health_condition, q.relationship_condition, q.family_problem,
            q.depression_level, q.anxiety_level, q.mental_support,
            q.self_harm_history, q.model_output, assessment_id,
        ))

    # --- Voice ফলাফল লেখা হচ্ছে (যদি সাবমিট করা হয়ে থাকে) ---
    if data.voice is not None:
        v = data.voice
        cur.execute("""
            UPDATE voice_results
            SET applicable = 1, file_path = ?, model_output = ?,
                confidence_percent = ?, risk_level = ?
            WHERE assessment_id = ?
        """, (v.file_path, v.model_output, v.confidence_percent, v.risk_level, assessment_id))

    # --- Handwriting ফলাফল লেখা হচ্ছে (যদি সাবমিট করা হয়ে থাকে) ---
    if data.handwriting is not None:
        h = data.handwriting
        cur.execute("""
            UPDATE handwriting_results
            SET applicable = 1, file_path = ?, model_output = ?,
                confidence_percent = ?, risk_level = ?
            WHERE assessment_id = ?
        """, (h.file_path, h.model_output, h.confidence_percent, h.risk_level, assessment_id))

    # --- সব লেখা শেষ, এখন assessment টা চিরতরে লক করে দেওয়া হচ্ছে ---
    cur.execute("UPDATE assessments SET is_finalized = 1 WHERE assessment_id = ?", (assessment_id,))

    conn.commit()
    conn.close()
    return {"success": True}


@app.post("/api/assessments/questionnaire")
def api_submit_questionnaire(data: QuestionnaireRequest, request: Request):
    """
    🔄 বদলে গেছে: আগে এই endpoint ML prediction চালিয়ে সরাসরি ডেটাবেজে
    লিখে দিত। এখন এটা শুধু prediction চালিয়ে ফলাফল রিটার্ন করে - কোনো
    DB write হয় না। ফলাফলটা frontend (assessment.js) এ সাময়িকভাবে জমা
    থাকে, এবং শুধু সবার নিচের "Save Assessment" বাটনে ক্লিক করলেই
    (নিচের /finalize endpoint দিয়ে) আসলে ডেটাবেজে লেখা হয়। এতে ইউজার
    Predict বাটনে ক্লিক করলেই যেন "auto-save" মনে না হয়, সেটা ঠিক হলো -
    আসল save শুধু Save বাটনেই হবে।
    """
    if not require_login(request):
        raise HTTPException(status_code=401, detail="Login required")

    answers = data.dict()
    assessment_id = answers.pop("assessment_id")

    # assessment টা আসলেই আছে কিনা এবং আগেই Save/Finalize হয়ে গেছে
    # কিনা চেক করা হচ্ছে (finalize হয়ে গেলে নতুন করে predict করারও
    # মানে নেই, যেহেতু resubmit করা যাবে না)
    conn = database.get_connection()
    cur = conn.cursor()
    current_status = _get_is_finalized(cur, assessment_id)
    conn.close()
    if current_status is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    if current_status == 1:
        return JSONResponse(
            {"success": False, "message": "এই Assessment আগেই Save হয়ে গেছে, তাই এডিট করা যাবে না।"},
            status_code=400,
        )

    # --- ML মডেলে input পাঠিয়ে prediction (output word) নেওয়া হচ্ছে ---
    prediction = ml_models.predict_questionnaire(answers)

    # 🆕 কোনো ডেটাবেজ write নেই এখানে - শুধু prediction ফেরত পাঠানো হচ্ছে
    return {"success": True, "model_output": prediction}


@app.post("/api/assessments/voice")
async def api_submit_voice(
    request: Request,
    assessment_id: int = Form(...),
    positive_file: UploadFile = File(...),
    negative_file: UploadFile = File(...),
    neutral_file: UploadFile = File(...),
):
    """
    EATD-Corpus paper অনুযায়ী মডেলটা ১টা না, ৩টা audio (positive/negative/
    neutral response) নিয়ে prediction দেয়। তাই এই endpoint এখন ৩টা আলাদা
    file নেয়, সেভ করে, ML মডেলে (এই ক্রমেই) পাঠিয়ে prediction নেয়।

    🔄 বদলে গেছে: ফাইল ডিস্কে সেভ হয় ও prediction চলে (এগুলো এড়ানো যায়
    না, prediction চালাতে ফাইল লাগে), কিন্তু voice_results টেবিলে আর
    কিছু লেখা হয় না। ডেটাবেজে আসল save শুধু "Save Assessment" বাটনে
    ক্লিক করলে (/finalize endpoint) হবে।
    """
    # ⚠️ লগইন চেক - questionnaire endpoint এর মতোই আগে এখানেও ছিল না
    if not require_login(request):
        raise HTTPException(status_code=401, detail="Login required")

    # --- ফাইল সেভ করার আগেই finalized/লক অবস্থা চেক করে নিচ্ছি ---
    # এতে অযথা ফাইল ডিস্কে সেভ হয়ে যাবে না যদি assessment টা আগেই
    # Save/লক হয়ে থাকে (নাহলে ডিস্কে "orphan"/অকেজো ফাইল জমা হতো)
    check_conn = database.get_connection()
    check_cur = check_conn.cursor()
    current_status = _get_is_finalized(check_cur, assessment_id)
    check_conn.close()
    if current_status is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    if current_status == 1:
        return JSONResponse(
            {"success": False, "message": "এই Assessment আগেই Save হয়ে গেছে, তাই এডিট করা যাবে না।"},
            status_code=400,
        )

    os.makedirs(VOICE_UPLOAD_DIR, exist_ok=True)

    saved_paths = {}
    for label, upload in [
        ("positive", positive_file),
        ("negative", negative_file),
        ("neutral", neutral_file),
    ]:
        # প্রতিটা ফাইলের নাম unique রাখার জন্য uuid ব্যবহার করা হলো
        file_extension = os.path.splitext(upload.filename)[1]
        unique_filename = f"{label}_{uuid.uuid4().hex}{file_extension}"
        save_path = os.path.join(VOICE_UPLOAD_DIR, unique_filename)

        with open(save_path, "wb") as buffer:
            shutil.copyfileobj(upload.file, buffer)

        saved_paths[label] = {
            "abs": save_path,
            "rel": f"/static/uploads/voice/{unique_filename}",
        }

    # --- ML মডেলে পাঠানো (positive, negative, neutral ক্রম বজায় রেখে) ---
    result = ml_models.predict_voice(
        saved_paths["positive"]["abs"],
        saved_paths["negative"]["abs"],
        saved_paths["neutral"]["abs"],
    )

    # ডেটাবেজের file_path column একটাই (TEXT) - তাই ৩টা path একসাথে
    # সেমিকোলন দিয়ে জোড়া লাগিয়ে একটা string হিসেবে সেভ করা হচ্ছে
    combined_paths = ";".join([
        saved_paths["positive"]["rel"],
        saved_paths["negative"]["rel"],
        saved_paths["neutral"]["rel"],
    ])

    # 🆕 এখানে আর কোনো ডেটাবেজ write নেই! ফাইলগুলো ডিস্কে সেভ হয়ে গেছে
    # (মডেলকে দিয়ে prediction চালাতে সেটা দরকার ছিল), কিন্তু voice_results
    # টেবিলে কিছু লেখা হচ্ছে না - সেটা শুধু "Save Assessment" বাটনে
    # ক্লিক করলে হবে (/finalize endpoint এ)। তাই এখানে file_path
    # (combined_paths) সহ পুরো ফলাফল frontend কে ফেরত পাঠিয়ে দেওয়া
    # হচ্ছে, যাতে assessment.js এটা মনে রেখে পরে Save করার সময় বান্ডেলে পাঠাতে পারে।
    return {"success": True, "file_path": combined_paths, **result}


@app.post("/api/assessments/handwriting")
async def api_submit_handwriting(
    request: Request,
    assessment_id: int = Form(...),
    handwriting_file: UploadFile = File(...),
):
    """
    Handwriting (৩য় মডেল) - ইনপুট এখন আর ছবি (image) না, বরং একটা .txt
    ফাইল যার ভেতরে কমা (,) দিয়ে আলাদা করা সংখ্যা (numeric feature values)
    থাকে। যেমন ফাইলের ভেতরের content এরকম হবে: 12,0.45,3,7.8,2,0.91

    ধাপগুলো:
        ১) .txt ফাইলটা আগের মতোই ডিস্কে সেভ করে রাখা হচ্ছে (prediction
           চালাতে ফাইলটা লাগে, আর রেকর্ড/audit trail হিসেবেও কাজে লাগে)
        ২) ফাইলের ভেতরের text পড়ে কমা (,) দিয়ে split করে প্রতিটা অংশকে
           float এ কনভার্ট করা হচ্ছে -> একটা numeric feature list তৈরি হয়
        ৩) সেই feature list ml_models.predict_handwriting() এ পাঠানো হচ্ছে
        ৪) prediction ফেরত পাঠানো হচ্ছে

        🔄 বদলে গেছে: prediction ডেটাবেজে সরাসরি সেভ হয় না আর - শুধু
        "Save Assessment" বাটনে ক্লিক করলে (/finalize endpoint) সেভ হবে।
    """
    # ⚠️ লগইন চেক - অন্য দুইটা submit endpoint এর মতোই
    if not require_login(request):
        raise HTTPException(status_code=401, detail="Login required")

    # --- ফাইল সেভ করার আগেই finalized/লক অবস্থা চেক করা হচ্ছে ---
    check_conn = database.get_connection()
    check_cur = check_conn.cursor()
    current_status = _get_is_finalized(check_cur, assessment_id)
    check_conn.close()
    if current_status is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    if current_status == 1:
        return JSONResponse(
            {"success": False, "message": "এই Assessment আগেই Save হয়ে গেছে, তাই এডিট করা যাবে না।"},
            status_code=400,
        )

    os.makedirs(HANDWRITING_UPLOAD_DIR, exist_ok=True)

    # ফাইলের extension যা-ই দেওয়া থাকুক (.txt না থাকলেও), আমরা এটাকে
    # আলাদা করে চিনতে পারার জন্য নিজে থেকেই .txt বসিয়ে দিচ্ছি
    file_extension = os.path.splitext(handwriting_file.filename)[1] or ".txt"
    unique_filename = f"{uuid.uuid4().hex}{file_extension}"
    save_path = os.path.join(HANDWRITING_UPLOAD_DIR, unique_filename)

    # --- ধাপ ১: ফাইলটা ডিস্কে সেভ করা হচ্ছে ---
    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(handwriting_file.file, buffer)

    # --- ধাপ ২: ফাইলের content পড়ে কমা দিয়ে আলাদা করা সংখ্যাগুলো বের করা হচ্ছে ---
    # 🐛 বাগ ফিক্স: আগে এখানে try/except ছিল না, তাই ইউজার ভুল করে কোনো
    # binary ফাইল (যেমন .docx কে রিনেম করে .txt বানিয়ে) আপলোড করলে
    # UnicodeDecodeError দিয়ে সরাসরি 500 crash হতো। এখন সেটা ধরে
    # পরিষ্কার একটা error message দেখানো হচ্ছে।
    try:
        with open(save_path, "r", encoding="utf-8") as f:
            raw_content = f.read()
    except UnicodeDecodeError:
        return JSONResponse(
            {"success": False,
             "message": "ফাইলটা পড়া যায়নি - এটা আসলেই একটা টেক্সট (.txt) ফাইল কিনা নিশ্চিত করো।"},
            status_code=400,
        )

    try:
        # উদাহরণ: " 12, 0.45 ,3,7.8" -> ["12", "0.45", "3", "7.8"]
        #          -> [12.0, 0.45, 3.0, 7.8]
        # strip() দিয়ে extra space/newline সামলানো হচ্ছে, খালি অংশ বাদ দেওয়া হচ্ছে
        feature_values = [
            float(value.strip())
            for value in raw_content.strip().split(",")
            if value.strip() != ""
        ]
    except ValueError:
        # ফাইলে সংখ্যা ছাড়া অন্য কিছু (যেমন অক্ষর) থাকলে এখানে ধরা পড়বে -
        # 500 error না দিয়ে বরং একটা পরিষ্কার, বোধগম্য error message পাঠানো হচ্ছে
        return JSONResponse(
            {"success": False,
             "message": "ফাইলে শুধু কমা দিয়ে আলাদা করা সংখ্যা থাকতে হবে (যেমন: 12,0.45,3)"},
            status_code=400,
        )

    if len(feature_values) == 0:
        # ফাইল খালি অথবা কোনো valid সংখ্যা খুঁজে পাওয়া যায়নি
        return JSONResponse(
            {"success": False, "message": "ফাইলটা খালি অথবা কোনো valid সংখ্যা পাওয়া যায়নি"},
            status_code=400,
        )

    # --- ধাপ ২.৫: feature সংখ্যা ঠিক আছে কিনা চেক করা হচ্ছে ---
    # darwin_feature_names.json লোড থাকলে সেখান থেকে ঠিক কতগুলো সংখ্যা
    # (৪৫০টা) লাগবে সেটা জানা যায়। কম/বেশি দিলে ভুল prediction আসবে,
    # তাই আগেই আটকে দিয়ে পরিষ্কার error দেখানো হচ্ছে।
    expected_count = ml_models.get_handwriting_feature_count()
    if expected_count is not None and len(feature_values) != expected_count:
        return JSONResponse(
            {"success": False,
             "message": f"ফাইলে {expected_count}টা সংখ্যা থাকা দরকার, পাওয়া গেছে {len(feature_values)}টা"},
            status_code=400,
        )

    # --- ধাপ ৩: ML মডেলে feature list পাঠিয়ে prediction নেওয়া হচ্ছে ---
    # (voice model এর মতোই এখন এটা একটা dict রিটার্ন করে -
    #  prediction, confidence_percent, probabilities, risk_level, message)
    result = ml_models.predict_handwriting(feature_values)

    # --- ধাপ ৪: 🆕 ডেটাবেজে আর এখানে কিছু লেখা হচ্ছে না ---
    # ফাইলটা ডিস্কে সেভ হয়ে গেছে (ধাপ ১ এ), prediction ও হয়ে গেছে,
    # কিন্তু handwriting_results টেবিলে write করা হচ্ছে না - সেটা শুধু
    # "Save Assessment" বাটনে ক্লিক করলে (/finalize endpoint) হবে।
    # তাই file_path সহ পুরো ফলাফল frontend কে ফেরত পাঠানো হচ্ছে।
    relative_path = f"/static/uploads/handwriting/{unique_filename}"

    # সম্পূর্ণ result dict (prediction + confidence + risk_level + message)
    # ফেরত পাঠানো হচ্ছে যাতে frontend এ voice এর মতোই richer output দেখানো যায়।
    # সাথে "model_output" key-টাও আলাদাভাবে যোগ করা হচ্ছে (result["prediction"]
    # এর সমান মান) - কারণ পুরোনো frontend কোড হয়তো "model_output" নামে
    # field খুঁজছে (questionnaire endpoint এর প্যাটার্নে), সেটা যাতে ভেঙে না যায়।
    return {
        "success": True,
        "model_output": result["prediction"],
        "file_path": relative_path,
        **result,
    }
