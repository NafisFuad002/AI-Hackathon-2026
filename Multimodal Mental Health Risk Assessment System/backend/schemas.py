"""
schemas.py
-----------
Pydantic মডেল (schema) - এগুলো দিয়ে FastAPI নিজে থেকেই যাচাই করে যে
frontend থেকে যে data আসছে সেটার ধরণ (type) ঠিক আছে কিনা।
এগুলোকে ML model এর সাথে গুলিয়ে ফেলো না - এগুলো শুধু request/response
এর "shape" বা কাঠামো নির্ধারণ করে।
"""

from pydantic import BaseModel, EmailStr
from typing import Optional


class LoginRequest(BaseModel):
    email: str
    password: str
    remember_me: bool = False


class ForgotPasswordEmailRequest(BaseModel):
    email: str


class SecurityAnswerRequest(BaseModel):
    professional_id: int
    answer: str


class ResetPasswordRequest(BaseModel):
    professional_id: int
    new_password: str


class NewStudentRequest(BaseModel):
    student_id: str
    name: str
    email: Optional[str] = None
    phone_number: Optional[str] = None
    department: Optional[str] = None
    batch: Optional[str] = None
    semester: Optional[str] = None
    section: Optional[str] = None
    blood_group: Optional[str] = None
    date_of_birth: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None


# =====================================================================
# ADMIN PANEL এর জন্য নতুন schema (Professional create/delete এর জন্য)
# =====================================================================

class AdminLoginRequest(BaseModel):
    """Admin panel এ লগইন করার জন্য - id/password শুধু 'admin'/'admin' (হার্ডকোডেড)।"""
    username: str
    password: str


class AdminCreateProfessionalRequest(BaseModel):
    """Admin panel থেকে নতুন Professional (যিনি assessment নেন) একাউন্ট তৈরির জন্য।"""
    name: str
    email: str
    phone_number: Optional[str] = None
    gender: Optional[str] = None
    nid: Optional[str] = None
    blood_group: Optional[str] = None
    password: str
    security_question: str
    security_answer: str


class QuestionnaireRequest(BaseModel):
    assessment_id: int
    age: int
    gender: str
    stress_level: str
    academic_performance: str
    health_condition: str
    relationship_condition: str
    family_problem: str
    depression_level: str
    anxiety_level: str
    mental_support: str
    self_harm_history: str


# =====================================================================
# 🆕 "SAVE ASSESSMENT" বাটনের জন্য নতুন schema
# ---------------------------------------------------------------------
# আগে প্রতিটা প্যানেলের "Submit & Predict" বাটন সরাসরি ডেটাবেজে লিখে
# দিত। এখন সেটা বদলে দেওয়া হলো - প্যানেলের বাটনগুলো শুধু prediction
# চালিয়ে ফলাফল দেখায় (কোনো DB write হয় না), আর ফলাফলগুলো frontend এ
# (assessment.js) সাময়িকভাবে জমা থাকে। শুধুমাত্র সবার নিচের "Save
# Assessment" বাটনে ক্লিক করলে - তখন এই তিনটা ফলাফল (যেগুলো আসলে
# সাবমিট করা হয়েছে) একসাথে বান্ডেল করে এই schema দিয়ে backend এ পাঠানো
# হয়, আর backend তখন একবারেই সব ডেটাবেজে লেখে এবং assessment টা লক
# করে দেয়।
# =====================================================================

class QuestionnaireResultData(BaseModel):
    """Questionnaire প্যানেলের ফলাফল - Save করার সময় বান্ডেলে পাঠানো হয়।"""
    age: int
    gender: str
    stress_level: str
    academic_performance: str
    health_condition: str
    relationship_condition: str
    family_problem: str
    depression_level: str
    anxiety_level: str
    mental_support: str
    self_harm_history: str
    model_output: str


class VoiceResultData(BaseModel):
    """Voice প্যানেলের ফলাফল - ফাইলগুলো predict করার সময়ই ডিস্কে সেভ হয়ে
    গিয়েছিল, এখানে শুধু সেই path আর prediction/confidence/risk_level পাঠানো হয়।"""
    file_path: str
    model_output: str
    confidence_percent: Optional[float] = None
    risk_level: Optional[str] = None


class HandwritingResultData(BaseModel):
    """Handwriting প্যানেলের ফলাফল - VoiceResultData এর মতোই গঠন।"""
    file_path: str
    model_output: str
    confidence_percent: Optional[float] = None
    risk_level: Optional[str] = None


class FinalizeAssessmentRequest(BaseModel):
    """
    Save Assessment বাটনের রিকোয়েস্ট বডি। তিনটাই Optional - কারণ
    ইউজার একটা, দুইটা বা তিনটাই প্যানেল সাবমিট করে থাকতে পারে
    (compulsory না)। যেটা সাবমিট করা হয়নি সেটার মান None/null থাকবে,
    আর backend সেটার জন্য কিছু আপডেট করবে না (applicable=0 রেখে দেবে)।
    """
    questionnaire: Optional[QuestionnaireResultData] = None
    voice: Optional[VoiceResultData] = None
    handwriting: Optional[HandwritingResultData] = None
