/* =====================================================================
   assessment.js
   --------------
   Assessment পেজের ৩টা প্যানেলের (Questionnaire / Voice / Handwriting)
   সাবমিট লজিক এখানে। প্রতিটা প্যানেল স্বাধীনভাবে (independently) কাজ
   করে - একটা সাবমিট না করলেও অন্যগুলো সাবমিট করা যায় (compulsory না)।

   🔄 বড় পরিবর্তন (এইবার): আগে প্রতিটা প্যানেলের "Submit & Predict"
   বাটনে ক্লিক করলেই ফলাফল সরাসরি ডেটাবেজে লেখা হয়ে যেত - যেটা ইউজারের
   কাছে "auto-save" মনে হচ্ছিল, যদিও সবার নিচের "Save Assessment"
   বাটনে ক্লিক করা হয়নি। এখন সেটা ঠিক করা হলো:

   - প্রতিটা প্যানেলের বাটন এখন শুধু ML prediction চালায় এবং ফলাফল
     স্ক্রিনে দেখায় - কোনো ডেটাবেজ write হয় না।
   - প্রতিটা প্যানেলের ফলাফল (questionnaireResult / voiceResult /
     handwritingResult ভ্যারিয়েবলে) এই পেজেই সাময়িকভাবে মনে রাখা হয়।
   - শুধুমাত্র সবার নিচের "Save Assessment" বাটনে ক্লিক করলে - তখন
     যেগুলো আসলে সাবমিট করা হয়েছিল (null না) সেগুলো একসাথে বান্ডেল
     করে backend এ পাঠানো হয়, এবং backend তখন একবারেই সব ডেটাবেজে
     লেখে এবং assessment টা লক করে দেয়। এর আগে পর্যন্ত ডেটাবেজে
     কিচ্ছু লেখা হয় না।

   ⚠️ একটা জিনিস মাথায় রাখা দরকার: ইউজার যদি প্যানেল সাবমিট করার পর
   Save বাটনে ক্লিক না করেই পেজ ছেড়ে চলে যায় (রিলোড/অন্য পেজে যায়),
   তাহলে সেই সাময়িক ফলাফল (browser memory তে থাকা) হারিয়ে যাবে -
   কারণ সেটা তো ডেটাবেজেই লেখা হয়নি। এটাই স্বাভাবিক এবং কাম্য আচরণ
   (ইউজার নিজেই যা চেয়েছে) - Save না করলে কিছুই "সেভ" থাকবে না।
   ===================================================================== */

const assessmentId = document.getElementById("assessment-id-value").value;

// 🆕 তিনটা প্যানেলের ফলাফল সাময়িকভাবে মনে রাখার জন্য ভ্যারিয়েবল।
// শুরুতে null - মানে "এখনো সাবমিট করা হয়নি"। যেটা সাবমিট করা হবে,
// সেটার ভ্যারিয়েবলে ডেটা বসে যাবে; Save বাটনে ক্লিক করলে এগুলো
// থেকেই backend এ পাঠানোর বান্ডেল তৈরি হবে।
let questionnaireResult = null;
let voiceResult = null;
let handwritingResult = null;

/* -----------------------------------------------------------------
   ছোট্ট helper ফাংশন: fetch() চলাকালীন একটা বাটনকে "processing" অবস্থায়
   নিয়ে যায় (disable + টেক্সট বদলে "Processing..." + CSS ক্লাস যোগ),
   আর কাজ শেষ হলে (success/fail যাই হোক) আগের অবস্থায় ফিরিয়ে আনার একটা
   ফাংশনও রিটার্ন করে।
   ----------------------------------------------------------------- */
function setButtonProcessing(button, processingText = "Processing...") {
    const originalText = button.textContent;
    button.disabled = true;
    button.classList.add("btn-processing");
    button.textContent = processingText;

    return function restoreButton() {
        button.disabled = false;
        button.classList.remove("btn-processing");
        button.textContent = originalText;
    };
}

// -------------------------------------------------------------------
// 1) QUESTIONNAIRE ASSESSMENT - শুধু Predict, ডেটাবেজে সেভ হয় না
// -------------------------------------------------------------------
document.getElementById("submit-questionnaire-btn").addEventListener("click", async () => {
    const btn = document.getElementById("submit-questionnaire-btn");
    const restoreButton = setButtonProcessing(btn, "Predicting...");

    // প্রতিটা dropdown/input থেকে মান সংগ্রহ করছি
    const answers = {
        age: parseInt(document.getElementById("q-age").value),
        gender: document.getElementById("q-gender").value,
        stress_level: document.getElementById("q-stress_level").value,
        academic_performance: document.getElementById("q-academic_performance").value,
        health_condition: document.getElementById("q-health_condition").value,
        relationship_condition: document.getElementById("q-relationship_condition").value,
        family_problem: document.getElementById("q-family_problem").value,
        depression_level: document.getElementById("q-depression_level").value,
        anxiety_level: document.getElementById("q-anxiety_level").value,
        mental_support: document.getElementById("q-mental_support").value,
        self_harm_history: document.getElementById("q-self_harm_history").value,
    };

    const payload = { assessment_id: parseInt(assessmentId), ...answers };

    try {
        const response = await fetch("/api/assessments/questionnaire", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        const data = await response.json();

        const resultBox = document.getElementById("questionnaire-result");

        if (data.success) {
            // 🐛 আগে এখানে "(এখনো Save হয়নি...)" টেক্সট জোড়া লাগানো হতো,
            // ইউজারের অনুরোধে বাদ দেওয়া হলো - শুধু result দেখানো হচ্ছে
            resultBox.textContent = `Result: ${data.model_output}`;

            // 🆕 ডেটাবেজে যাওয়ার বদলে এখানেই (browser memory তে) ফলাফলটা
            // মনে রাখা হচ্ছে, যাতে Save বাটনে ক্লিক করলে এটা পাঠানো যায়
            questionnaireResult = { ...answers, model_output: data.model_output };
        } else {
            resultBox.textContent = data.message || "Predict করা যায়নি।";
        }
        resultBox.classList.remove("hidden");
    } catch (err) {
        alert("Something Wrong, Try Again");
    } finally {
        restoreButton();
    }
});

// -------------------------------------------------------------------
// 2) VOICE ASSESSMENT - শুধু Predict, ডেটাবেজে সেভ হয় না
// -------------------------------------------------------------------
// মডেল ৩টা আলাদা audio (positive/negative/neutral response) নেয় - paper
// অনুযায়ী GRU মডেল ট্রেনিং হয়েছে এই ৩টা response এর sequence দিয়ে।
document.getElementById("submit-voice-btn").addEventListener("click", async () => {
    const positiveInput = document.getElementById("voice-positive-input");
    const negativeInput = document.getElementById("voice-negative-input");
    const neutralInput = document.getElementById("voice-neutral-input");

    if (
        positiveInput.files.length === 0 ||
        negativeInput.files.length === 0 ||
        neutralInput.files.length === 0
    ) {
        alert("Please select all (Positive, Negative, Neutral) voice files");
        return;
    }

    const btn = document.getElementById("submit-voice-btn");
    const restoreButton = setButtonProcessing(btn, "Analyzing voice...");

    // ফাইল আপলোডের জন্য JSON না, FormData ব্যবহার করতে হয়
    const formData = new FormData();
    formData.append("assessment_id", assessmentId);
    formData.append("positive_file", positiveInput.files[0]);
    formData.append("negative_file", negativeInput.files[0]);
    formData.append("neutral_file", neutralInput.files[0]);

    try {
        const response = await fetch("/api/assessments/voice", {
            method: "POST",
            body: formData,
        });
        const data = await response.json();

        const resultBox = document.getElementById("voice-result");
        if (data.success) {
            // 🐛 আগে এখানে "- এখনো Save হয়নি..." টেক্সট জোড়া লাগানো হতো,
            // ইউজারের অনুরোধে বাদ দেওয়া হলো - শুধু result দেখানো হচ্ছে
            resultBox.textContent =
                `${data.prediction} (${data.confidence_percent}% confidence, ${data.risk_level} risk)`;

            // 🆕 ফাইল ইতিমধ্যে ডিস্কে সেভ হয়ে গেছে (prediction চালাতে
            // দরকার ছিল), কিন্তু voice_results টেবিলে কিছু লেখা হয়নি।
            // সেই file_path + prediction ফলাফল এখানে মনে রাখা হচ্ছে।
            voiceResult = {
                file_path: data.file_path,
                model_output: data.prediction,
                confidence_percent: data.confidence_percent,
                risk_level: data.risk_level,
            };
        } else {
            resultBox.textContent = data.message || "Prediction Failed, Try Again";
        }
        resultBox.classList.remove("hidden");
    } catch (err) {
        alert("Something Wrong, Try Again");
    } finally {
        restoreButton();
    }
});

// -------------------------------------------------------------------
// 3) HANDWRITING ASSESSMENT - শুধু Predict, ডেটাবেজে সেভ হয় না
// -------------------------------------------------------------------
document.getElementById("submit-handwriting-btn").addEventListener("click", async () => {
    const fileInput = document.getElementById("handwriting-file-input");
    if (fileInput.files.length === 0) {
        alert("Please select a handwriting file");
        return;
    }

    const btn = document.getElementById("submit-handwriting-btn");
    const restoreButton = setButtonProcessing(btn, "Analyzing...");

    const formData = new FormData();
    formData.append("assessment_id", assessmentId);
    formData.append("handwriting_file", fileInput.files[0]);

    try {
        const response = await fetch("/api/assessments/handwriting", {
            method: "POST",
            body: formData,
        });
        const data = await response.json();

        const resultBox = document.getElementById("handwriting-result");
        if (data.success) {
            // 🐛 আগে এখানে "(এখনো Save হয়নি...)" টেক্সট জোড়া লাগানো হতো,
            // ইউজারের অনুরোধে বাদ দেওয়া হলো - শুধু result দেখানো হচ্ছে
            resultBox.textContent = `Result: ${data.model_output}`;

            // 🆕 ফলাফল মনে রাখা হচ্ছে, ডেটাবেজে এখনো কিছু লেখা হয়নি
            handwritingResult = {
                file_path: data.file_path,
                model_output: data.model_output,
                confidence_percent: data.confidence_percent,
                risk_level: data.risk_level,
            };
        } else {
            resultBox.textContent = data.message || "Prediction Failed";
        }
        resultBox.classList.remove("hidden");
    } catch (err) {
        alert("Something Wrong, Try Again");
    } finally {
        restoreButton();
    }
});

// -------------------------------------------------------------------
// 4) SAVE ASSESSMENT - এখানেই আসল ডেটাবেজ write + লক হয়
// -------------------------------------------------------------------
// এই বাটনে ক্লিক করলে - এতক্ষণ যা যা প্যানেল সাবমিট/predict করা
// হয়েছিল (questionnaireResult/voiceResult/handwritingResult - যেগুলো
// null না), সেগুলো একসাথে বান্ডেল করে /finalize endpoint এ পাঠানো
// হয়। backend তখন এই বান্ডেল থেকে ডেটাবেজে লেখে এবং assessment টা
// চিরতরে লক করে দেয়। এটাই একমাত্র জায়গা যেখানে আসলে "Save" হয়।
const saveAssessmentBtn = document.getElementById("save-assessment-btn");
if (saveAssessmentBtn) {
    saveAssessmentBtn.addEventListener("click", async () => {
        // কিছুই সাবমিট/predict করা না থাকলে ইউজারকে জানিয়ে দেওয়া হচ্ছে,
        // যাতে ভুলে খালি assessment সেভ করে না ফেলে
        if (!questionnaireResult && !voiceResult && !handwritingResult) {
            alert("এখনো কোনো প্যানেল (Questionnaire/Voice/Handwriting) সাবমিট করা হয়নি। অন্তত একটা প্যানেলে Submit/Upload & Predict চেপে ফলাফল দেখার পর Save করো।");
            return;
        }

        const confirmed = confirm(
            "একবার Save করলে আর এই Assessment এডিট করা যাবে না। তুমি কি নিশ্চিত?"
        );
        if (!confirmed) return;

        const restoreButton = setButtonProcessing(saveAssessmentBtn, "Saving...");

        // 🆕 এতক্ষণ মনে রাখা তিনটা ফলাফল থেকে বান্ডেল তৈরি করা হচ্ছে -
        // যেটা সাবমিট করা হয়নি সেটা null-ই থেকে যাবে, backend সেটার
        // জন্য কিছু লিখবে না
        const bundlePayload = {
            questionnaire: questionnaireResult,
            voice: voiceResult,
            handwriting: handwritingResult,
        };

        try {
            const response = await fetch(`/api/assessments/${assessmentId}/finalize`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(bundlePayload),
            });
            const data = await response.json();

            if (data.success) {
                // Save সফল হলে পেজ রিলোড করা হচ্ছে - backend এখন
                // is_finalized = 1 দেখে read-only ভিউ রেন্ডার করে দেবে,
                // যেখানে এইমাত্র সেভ হওয়া ফলাফলগুলোই দেখা যাবে
                window.location.reload();
            } else {
                alert(data.message || "Save করা যায়নি, আবার চেষ্টা করো।");
                restoreButton();
            }
        } catch (err) {
            alert("Something Wrong, Try Again");
            restoreButton();
        }
    });
}
