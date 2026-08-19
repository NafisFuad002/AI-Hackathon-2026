"""
ml_models.py
-------------
তোমার ৩টা .pkl মডেল লোড করে prediction (একটা word) রিটার্ন করার লজিক
এখানে আছে।

⚠️ গুরুত্বপূর্ণ নোট (অবশ্যই পড়ো):
    আমার কাছে তোমার আসল .pkl ফাইলগুলো এখনো নেই, তাই আমি "placeholder /
    mock" প্রেডিকশন লজিক দিয়ে রেখেছি যাতে পুরো ওয়েবসাইটটা এখনই run করে
    টেস্ট করতে পারো। তুমি যখন আসল .pkl ফাইল models_ml/ ফোল্ডারে রাখবে,
    তখন এই ফাইলটা স্বয়ংক্রিয়ভাবে (automatically) সেটা ব্যবহার করবে -
    আলাদা কিছু বদলাতে হবে না, শুধু নিচের CATEGORY_ENCODING ম্যাপটা
    তোমার training script এ যেভাবে encode করেছিলে সেভাবে মিলিয়ে নিতে হবে।

ফোল্ডার গঠন (models_ml/ এর ভেতরে এই নামে ফাইল রাখলেই কাজ করবে):
    backend/models_ml/questionnaire_model.pkl
    backend/models_ml/voice_model.pth
    backend/models_ml/handwriting_model.pkl   (৩য় মডেল)

৩য় মডেল (handwriting) এর ইনপুট ফরম্যাট এখন চূড়ান্ত (finalized):
    ইউজার একটা .txt ফাইল আপলোড করবে, যার ভেতরে কমা (,) দিয়ে আলাদা করা
    numeric feature values থাকবে (যেমন: 12,0.45,3,7.8,2,0.91)। main.py
    এই .txt ফাইলটা পড়ে, parse করে একটা Python list of float বানিয়ে
    predict_handwriting() ফাংশনে পাঠায় - এখানে সেটাকে sklearn মডেলের
    ইনপুটে (2D numpy array) রূপান্তর করে prediction বের করা হয়।

    ⚠️ .txt ফাইলে কতগুলো সংখ্যা থাকবে এবং কোন ক্রমে থাকবে, সেটা অবশ্যই
    handwriting_model.pkl ট্রেনিং এর সময় ব্যবহৃত feature order এর সাথে
    হুবহু মিলতে হবে - নাহলে prediction ভুল আসবে।
"""

import os
import pickle
import json
import joblib   # ⚠️ darwin_alzheimer_model.pkl আর darwin_label_encoder.pkl
                # এই দুইটা joblib দিয়ে সেভ করা - সাধারণ pickle.load() দিয়ে
                # এগুলো খোলা যায় না, তাই joblib.load() ব্যবহার করা হচ্ছে
import urllib.request  # 🆕 বড় (25MB+) মডেল ফাইল GitHub-এর সাধারণ website
                        # upload দিয়ে repo-তে রাখা যায় না (25MB limit), তাই
                        # সেগুলো GitHub "Release" এ আলাদাভাবে আপলোড করে সেখান
                        # থেকে সার্ভার চালু হওয়ার সময় ডাউনলোড করে আনা হয়
import numpy as np
import torch

# EATD-Corpus paper অনুযায়ী ট্রেনিং করা Voice model এর architecture +
# mel-extraction ফাংশন - এটা একটা PyTorch মডেল, questionnaire/handwriting
# এর মতো sklearn .pkl মডেল না, তাই আলাদাভাবে লোড করতে হয়।
from audio_model import AudioGRUNet, extract_mel

MODELS_DIR = os.path.join(os.path.dirname(__file__), "models_ml")

QUESTIONNAIRE_MODEL_PATH = os.path.join(MODELS_DIR, "questionnaire_model.pkl")
VOICE_MODEL_PATH = os.path.join(MODELS_DIR, "voice_model.pth")   # ⚠️ .pth, .pkl না!
# ৩য় মডেল (handwriting) - DARWIN dataset ভিত্তিক Alzheimer/risk-indicator
# classifier। এর জন্য ৩টা ফাইল লাগে - এই তিনটাই models_ml/ ফোল্ডারে থাকতে হবে:
HANDWRITING_MODEL_PATH = os.path.join(MODELS_DIR, "darwin_alzheimer_model.pkl")           # আসল classifier (sklearn Pipeline)
HANDWRITING_LABEL_ENCODER_PATH = os.path.join(MODELS_DIR, "darwin_label_encoder.pkl")     # 0/1 -> 'H'/'P' ডিকোড করার জন্য
HANDWRITING_FEATURE_NAMES_PATH = os.path.join(MODELS_DIR, "darwin_feature_names.json")    # ৪৫০টা feature এর নাম + ক্রম

# =====================================================================
# 🆕 QUESTIONNAIRE মডেল (suicide_risk_model.pkl) সাইজে বড় (৩৫+ MB) বলে
# GitHub রিপোর ভেতরে সরাসরি রাখা যায়নি (সাধারণ upload এ ২৫MB limit) -
# তাই এটা GitHub এর "Release" ফিচার দিয়ে আলাদাভাবে আপলোড করে রাখা হয়েছে,
# আর নিচের লিংক থেকে সেটা ডাউনলোড করে আনা হয়।
#
# এই লিংকটা একটা environment variable (QUESTIONNAIRE_MODEL_URL) থেকেও
# আসতে পারে - Render এ চাইলে সেটা সেট করে ভবিষ্যতে মডেল আপডেট করা যাবে,
# কোড না বদলিয়েই। এনভায়রনমেন্ট ভ্যারিয়েবল সেট করা না থাকলে নিচের
# ডিফল্ট লিংকটাই ব্যবহার হবে।
# =====================================================================
QUESTIONNAIRE_MODEL_DOWNLOAD_URL = os.environ.get(
    "QUESTIONNAIRE_MODEL_URL",
    "https://github.com/NafisFuad002/AI-Hackathon-2026/releases/download/suicide_risk_model/suicide_risk_model.pkl",
)


# =====================================================================
# ১১টা প্রশ্নের প্রতিটা categorical answer কে সংখ্যায় (number) রূপান্তর
# করার ম্যাপ। এটা তোমার ML model training এর সময় যেভাবে encode করা
# হয়েছিল, ঠিক সেভাবেই হতে হবে - নাহলে ভুল prediction আসবে!
#
# 👉 তুমি যখন আসল মডেল দেবে/training script শেয়ার করবে, তখন এই ম্যাপটা
#    আমি ঠিক করে দেব যাতে হুবহু তোমার dataset এর encoding এর সাথে মিলে।
#    আপাতত আমি একটা যৌক্তিক (alphabetical/logical order) ম্যাপিং বসিয়ে
#    দিয়েছি যাতে কোড এখনই কাজ করে।
# =====================================================================
CATEGORY_ENCODING = {
    "gender":                 {"Male": 0, "Female": 1},
    "stress_level":            {"Low": 0, "Moderate": 1, "High": 2},
    "academic_performance":    {"Poor": 0, "Average": 1, "Good": 2, "Excellent": 3},
    "health_condition":        {"Abnormal": 0, "Fair": 1, "Normal": 2},
    "relationship_condition":  {"Single": 0, "In a relationship": 1, "Breakup": 2},
    "family_problem":          {"None": 0, "Financial": 1, "Parental conflict": 2},
    "depression_level":        {"Sometimes": 0, "Often": 1, "Always": 2},
    "anxiety_level":           {"Sometimes": 0, "Often": 1, "Always": 2},
    "mental_support":          {"loneliness": 0, "Friends": 1, "Family": 2},
    "self_harm_history":       {"No": 0, "Yes": 1},
}

# মডেল যে ক্রমে (order) feature গুলো আশা করে, ঠিক সেই ক্রমটা এখানে
# লিখতে হবে। এটাও তোমার training script অনুযায়ী পরিবর্তন করতে হবে।
FEATURE_ORDER = [
    "age", "gender", "stress_level", "academic_performance",
    "health_condition", "relationship_condition", "family_problem",
    "depression_level", "anxiety_level", "mental_support",
    "self_harm_history",
]


def _ensure_model_downloaded(path, url):
    """
    🆕 দেওয়া path এ ফাইলটা আগে থেকে না থাকলে, দেওয়া url থেকে সেটা
    ডাউনলোড করে ওই path এ সেভ করে রাখে (একবারই হবে - পরের বার সার্ভার
    রিস্টার্ট হলে ফাইল আগে থেকে থাকায় আর ডাউনলোড হবে না)।

    এটা মূলত বড় সাইজের (২৫MB+) মডেল ফাইলের জন্য, যেগুলো সরাসরি GitHub
    রিপোতে রাখা যায়নি (GitHub Release এ আলাদাভাবে আপলোড করা আছে)।

    url ফাঁকা/None হলে বা ডাউনলোড কোনো কারণে ব্যর্থ হলে চুপচাপ ফিরে আসে -
    তখন _load_pickle_model() ফাইল খুঁজে না পেয়ে None রিটার্ন করবে এবং
    mock prediction ব্যবহার হবে (পুরো অ্যাপ ক্র্যাশ করবে না)।
    """
    if os.path.exists(path) or not url:
        return

    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        print(f"[ml_models.py] '{os.path.basename(path)}' পাওয়া যায়নি - ডাউনলোড করা হচ্ছে: {url}")
        urllib.request.urlretrieve(url, path)
        print(f"[ml_models.py] ডাউনলোড সম্পন্ন -> {path}")
    except Exception as e:
        # ডাউনলোড ব্যর্থ হলেও সার্ভার চালু রাখা হচ্ছে (mock prediction দিয়ে
        # কাজ চালানো যাবে) - শুধু error টা log এ দেখানো হচ্ছে যাতে বোঝা যায়
        print(f"[ml_models.py] ⚠️ মডেল ডাউনলোড ব্যর্থ হয়েছে ({path}): {e}")


def _load_pickle_model(path):
    """
    দেওয়া path এ .pkl ফাইল থাকলে সেটা লোড করে রিটার্ন করে।
    ফাইল না থাকলে None রিটার্ন করে (তখন আমরা mock prediction ব্যবহার করব)।
    """
    if os.path.exists(path):
        with open(path, "rb") as f:
            return pickle.load(f)
    return None


def _load_joblib_model(path):
    """
    joblib দিয়ে সেভ করা sklearn model/Pipeline/LabelEncoder লোড করে।
    (darwin_alzheimer_model.pkl এবং darwin_label_encoder.pkl - দুইটাই
    এই ফাংশন দিয়ে লোড হবে, কারণ এগুলো pickle.load() দিয়ে খোলা যায় না)
    ফাইল না থাকলে None রিটার্ন করে (তখন mock prediction ব্যবহার হবে)।
    """
    if os.path.exists(path):
        return joblib.load(path)
    return None


def _load_feature_names(path):
    """
    handwriting মডেলের ৪৫০টা feature এর নাম ও ক্রম (order) সম্বলিত JSON
    ফাইলটা লোড করে একটা Python list রিটার্ন করে। এটা মূলত validation এর
    জন্য ব্যবহার হয় - ইউজারের আপলোড করা .txt ফাইলে ঠিক কতগুলো সংখ্যা
    থাকা উচিত সেটা এখান থেকে বোঝা যায় (len(feature_names))।
    ফাইল না থাকলে None রিটার্ন করে (তখন feature count validate করা হবে না)।
    """
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def _load_voice_model(path):
    """
    Voice model টা PyTorch (.pth, state_dict) - questionnaire/handwriting এর
    মতো pickle.load() দিয়ে সরাসরি লোড করা যায় না। প্রথমে architecture
    (AudioGRUNet) বানিয়ে তারপর সেভ করা weight (state_dict) বসাতে হয়।
    ফাইল না থাকলে None রিটার্ন করে (তখন mock prediction ব্যবহার হবে)।
    """
    if not os.path.exists(path):
        return None
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = AudioGRUNet().to(device)
    state_dict = torch.load(path, map_location=device)
    model.load_state_dict(state_dict)
    model.eval()  # inference mode - dropout বন্ধ থাকবে
    return {"model": model, "device": device}


# অ্যাপ চালু হওয়ার সময় একবারই মডেলগুলো লোড করে মেমোরিতে রাখা হচ্ছে
# (প্রতিটা request এ বারবার লোড করলে সার্ভার স্লো হয়ে যাবে)

# 🆕 questionnaire মডেল (suicide_risk_model.pkl) সাইজে বড় বলে GitHub
# Release থেকে দরকার হলে প্রথমে ডাউনলোড করে নেওয়া হচ্ছে, তারপর লোড করা
# হচ্ছে - অন্য দুইটা মডেল (voice/handwriting) ছোট, তাই সরাসরি রিপোতেই
# আছে বলে ধরে নেওয়া হচ্ছে (আলাদা ডাউনলোড লাগছে না)
_ensure_model_downloaded(QUESTIONNAIRE_MODEL_PATH, QUESTIONNAIRE_MODEL_DOWNLOAD_URL)
_questionnaire_model = _load_pickle_model(QUESTIONNAIRE_MODEL_PATH)
_voice_model = _load_voice_model(VOICE_MODEL_PATH)   # PyTorch মডেল - আলাদা loader

# handwriting এর জন্য ৩টা জিনিসই লোড হচ্ছে - classifier, label encoder, feature names
_handwriting_model = _load_joblib_model(HANDWRITING_MODEL_PATH)
_handwriting_label_encoder = _load_joblib_model(HANDWRITING_LABEL_ENCODER_PATH)
_handwriting_feature_names = _load_feature_names(HANDWRITING_FEATURE_NAMES_PATH)


def get_handwriting_feature_count():
    """
    main.py থেকে ব্যবহার হয় - ইউজারের আপলোড করা .txt ফাইলে কয়টা সংখ্যা
    থাকা উচিত সেটা জানার জন্য (validation এর জন্য)। darwin_feature_names.json
    লোড না থাকলে None রিটার্ন করে (তখন main.py আর count check করবে না)।
    """
    if _handwriting_feature_names is not None:
        return len(_handwriting_feature_names)
    return None


def encode_questionnaire_answers(answers: dict):
    """
    Frontend থেকে আসা ১১টা answer (dict) কে মডেলের জন্য একটা numeric
    feature vector এ রূপান্তর করে।

    answers এর ভেতরে থাকবে: age (int) + বাকি ১০টা categorical answer (string)
    """
    feature_vector = []
    for feature_name in FEATURE_ORDER:
        raw_value = answers.get(feature_name)

        if feature_name == "age":
            # বয়স সরাসরি numeric, শুধু int এ কনভার্ট করলেই হয়
            feature_vector.append(int(raw_value))
        else:
            # বাকিগুলো categorical -> CATEGORY_ENCODING ম্যাপ থেকে সংখ্যা বের করি
            encoding_map = CATEGORY_ENCODING[feature_name]
            feature_vector.append(encoding_map.get(raw_value, 0))

    return np.array(feature_vector).reshape(1, -1)  # sklearn 2D input চায়


def predict_questionnaire(answers: dict) -> str:
    """
    ১১টা প্রশ্নের উত্তর নিয়ে মডেল থেকে একটা word (prediction) রিটার্ন করে।
    """
    if _questionnaire_model is not None:
        # ✅ আসল .pkl মডেল পাওয়া গেছে -> সত্যিকারের prediction
        features = encode_questionnaire_answers(answers)
        prediction = _questionnaire_model.predict(features)
        return str(prediction[0])
    else:
        # ⚠️ আসল মডেল এখনো আপলোড হয়নি -> সাধারণ rule-based mock prediction
        # (শুধু demo/testing এর জন্য, চূড়ান্ত ফলাফল নয়)
        risk_score = 0
        if answers.get("stress_level") == "High":
            risk_score += 1
        if answers.get("depression_level") == "Always":
            risk_score += 1
        if answers.get("anxiety_level") == "Always":
            risk_score += 1
        if answers.get("self_harm_history") == "Yes":
            risk_score += 2

        if risk_score >= 3:
            return "High-Risk"
        elif risk_score >= 1:
            return "Moderate-Risk"
        else:
            return "Low-Risk"


def predict_voice(positive_path: str, negative_path: str, neutral_path: str) -> dict:
    """
    EATD-Corpus paper (audio-only GRU model) অনুযায়ী prediction।

    ⚠️ গুরুত্বপূর্ণ: এই মডেল একটা না, ৩টা audio file নেয় - ঠিক এই ক্রমে
    (positive, negative, neutral) - কারণ মডেল ট্রেনিং হয়েছিল volunteer-
    দের ৩টা emotion-related response এর sequence দিয়ে। ক্রম ভুল হলে
    prediction ভুল আসবে।

    রিটার্ন করে একটা dict (শুধু string না) - এতে prediction, confidence,
    ও risk_level সবকিছু থাকে যাতে website এ human-readable ভাবে দেখানো যায়।
    """
    if _voice_model is not None:
        model = _voice_model["model"]
        device = _voice_model["device"]

        mels = [
            extract_mel(positive_path),
            extract_mel(negative_path),
            extract_mel(neutral_path),
        ]  # ৩টা audio থেকে mel spectrogram - অবশ্যই এই ক্রমে

        with torch.no_grad():
            logits = model([mels], device)
            probs = torch.softmax(logits, dim=1)[0]
            pred_idx = int(torch.argmax(probs).item())
            confidence = float(probs[pred_idx].item())

        class_names = ("Not Depressed", "Depressed")

        if pred_idx == 1:
            if confidence >= 0.80:
                risk_level = "High"
            elif confidence >= 0.60:
                risk_level = "Moderate"
            else:
                risk_level = "Low"
        else:
            risk_level = "Low"

        return {
            "prediction": class_names[pred_idx],
            "confidence_percent": round(confidence * 100, 1),
            "probabilities": {
                class_names[0]: round(float(probs[0].item()) * 100, 1),
                class_names[1]: round(float(probs[1].item()) * 100, 1),
            },
            "risk_level": risk_level,
            "message": (
                f"The analyzed voice sample shows a {risk_level.lower()} likelihood "
                f"of depressive indicators ({round(confidence * 100, 1)}% confidence)."
            ),
        }
    else:
        # ⚠️ voice_model.pth এখনো models_ml/ ফোল্ডারে নেই -> mock placeholder
        return {
            "prediction": "Normal",
            "confidence_percent": 0.0,
            "probabilities": {"Not Depressed": 0.0, "Depressed": 0.0},
            "risk_level": "Unknown",
            "message": "Voice model not loaded yet (models_ml/voice_model.pth missing).",
        }


def predict_handwriting(feature_values: list) -> dict:
    """
    Handwriting (৩য় মডেল - DARWIN dataset ভিত্তিক Pipeline: StandardScaler
    + SelectKBest + ExtraTreesClassifier) থেকে prediction রিটার্ন করে।

    ইনপুট: feature_values -> main.py তে ইউজারের আপলোড করা .txt ফাইল
    (কমা দিয়ে আলাদা করা ৪৫০টা সংখ্যা) থেকে parse করা list of float।
    এই ৪৫০টা সংখ্যার ক্রম অবশ্যই darwin_feature_names.json এর ক্রমের
    সাথে হুবহু মিলতে হবে (২৫টা handwriting task x ১৮টা feature = ৪৫০)।

    রিটার্ন করে একটা dict (predict_voice() এর একই প্যাটার্নে) - prediction,
    confidence, probabilities, risk_level, message - সব একসাথে, যাতে
    website এ human-readable ভাবে দেখানো যায়। prediction এর মান সরাসরি
    "Healthy" অথবা "Patient" হবে (DARWIN dataset এর নিজস্ব label অনুযায়ী)।
    """
    # 'H' (Healthy) / 'P' (Patient) - মডেলের raw label - কে ওয়েবসাইটে
    # সরাসরি এই নামেই দেখানো হবে (DARWIN dataset এর original label
    # অনুযায়ী - এটা Alzheimer's disease diagnosis এর জন্য ট্রেইন করা)
    LABEL_MAP = {"H": "Healthy", "P": "Patient"}

    if _handwriting_model is not None:
        # sklearn Pipeline সবসময় 2D input চায় (1 sample x N features)
        features = np.array(feature_values, dtype=float).reshape(1, -1)

        pred_encoded = _handwriting_model.predict(features)[0]  # 0 অথবা 1 (encoded)

        # label encoder দিয়ে সংখ্যাকে আবার 'H'/'P' এ ফিরিয়ে আনা হচ্ছে
        if _handwriting_label_encoder is not None:
            raw_label = _handwriting_label_encoder.inverse_transform([pred_encoded])[0]
        else:
            # label encoder ফাইল না থাকলে ধরে নিচ্ছি 1 = 'P', 0 = 'H'
            raw_label = "P" if pred_encoded == 1 else "H"

        prediction_label = LABEL_MAP.get(raw_label, str(raw_label))

        # confidence/probability বের করা হচ্ছে (মডেলে predict_proba থাকায় এটা কাজ করবে)
        if hasattr(_handwriting_model, "predict_proba"):
            probs = _handwriting_model.predict_proba(features)[0]
            # predict_proba এর column ক্রম label_encoder.classes_ অনুযায়ী সাজানো
            # (['H', 'P'] -> index 0 = Healthy এর probability, index 1 = Patient এর probability)
            classes = (_handwriting_label_encoder.classes_
                       if _handwriting_label_encoder is not None else np.array(["H", "P"]))
            prob_dict = {
                LABEL_MAP.get(c, c): round(float(p) * 100, 1)
                for c, p in zip(classes, probs)
            }
            confidence_percent = round(float(max(probs)) * 100, 1)
        else:
            prob_dict = {}
            confidence_percent = None

        # risk_level নির্ধারণ - "Patient" ক্লাসের probability অনুযায়ী
        patient_prob = prob_dict.get("Patient", 100.0 if prediction_label == "Patient" else 0.0)
        if patient_prob >= 80:
            risk_level = "High"
        elif patient_prob >= 50:
            risk_level = "Moderate"
        else:
            risk_level = "Low"

        return {
            "prediction": prediction_label,   # "Healthy" অথবা "Patient"
            "confidence_percent": confidence_percent,
            "probabilities": prob_dict,       # {"Healthy": .., "Patient": ..}
            "risk_level": risk_level,
            "message": (
                f"Handwriting pattern analysis result: {prediction_label} "
                f"({confidence_percent}% confidence)."
            ),
        }
    else:
        # ⚠️ darwin_alzheimer_model.pkl এখনো models_ml/ ফোল্ডারে নেই -> mock placeholder
        return {
            "prediction": "Healthy",
            "confidence_percent": 0.0,
            "probabilities": {},
            "risk_level": "Unknown",
            "message": "Handwriting model not loaded yet (models_ml/darwin_alzheimer_model.pkl missing).",
        }
