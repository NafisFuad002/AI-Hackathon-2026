/* =====================================================================
   login.js
   ---------
   লগইন পেজের সব interactivity এখানে। মূলত ৩টা কাজ করে:
     1) সাধারণ লগইন (এবং Demo Login)
     2) Forgot Password -> Security Question verify (lockout সহ)
     3) নতুন পাসওয়ার্ড সেট করা
   ===================================================================== */

// আমরা এই ভ্যারিয়েবলে সাময়িকভাবে professional_id রাখব, কারণ
// security question ধাপ থেকে reset password ধাপ পর্যন্ত এটা লাগবে
let currentProfessionalId = null;

// ---------- helper: তিনটা স্টেপের মধ্যে কোনটা দেখাবে সেটা কন্ট্রোল করে ----------
function showStep(stepId) {
    document.getElementById("login-step").classList.add("hidden");
    document.getElementById("security-step").classList.add("hidden");
    document.getElementById("reset-step").classList.add("hidden");
    document.getElementById(stepId).classList.remove("hidden");
}

// =========================================================================
// STEP 1: সাধারণ লগইন
// =========================================================================
document.getElementById("login-btn").addEventListener("click", async () => {
    const email = document.getElementById("login-email").value.trim();
    const password = document.getElementById("login-password").value;
    const errorBox = document.getElementById("login-error");
    const btn = document.getElementById("login-btn");

    // 🆕 প্রসেসিং অবস্থা দেখানো হচ্ছে - বাটন disable + টেক্সট বদলে
    // "Logging in..." যতক্ষণ না backend থেকে রেসপন্স আসে
    const originalText = btn.textContent;
    btn.disabled = true;
    btn.classList.add("btn-processing");
    btn.textContent = "Logging in...";

    try {
        const response = await fetch("/api/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, password }),
        });
        const data = await response.json();

        if (data.success) {
            window.location.href = data.redirect;  // Dashboard এ পাঠিয়ে দেয়
            // এখানে বাটন আর ফিরিয়ে আনার দরকার নেই কারণ পেজই বদলে যাচ্ছে
        } else {
            errorBox.textContent = data.message;
            errorBox.classList.remove("hidden");
            btn.disabled = false;
            btn.classList.remove("btn-processing");
            btn.textContent = originalText;
        }
    } catch (err) {
        errorBox.textContent = "কোনো সমস্যা হয়েছে, আবার চেষ্টা করো।";
        errorBox.classList.remove("hidden");
        btn.disabled = false;
        btn.classList.remove("btn-processing");
        btn.textContent = originalText;
    }
});

// =========================================================================
// STEP 2: FORGOT PASSWORD -> SECURITY QUESTION
// =========================================================================
document.getElementById("forgot-password-link").addEventListener("click", (e) => {
    e.preventDefault();
    showStep("security-step");
});

document.getElementById("back-to-login-btn").addEventListener("click", () => {
    showStep("login-step");
});

// Email দিয়ে security question বের করা
document.getElementById("get-question-btn").addEventListener("click", async () => {
    const email = document.getElementById("recovery-email").value.trim();
    const errorBox = document.getElementById("security-error");
    errorBox.classList.add("hidden");

    // 🆕 প্রসেসিং অবস্থা
    const btn = document.getElementById("get-question-btn");
    const originalText = btn.textContent;
    btn.disabled = true;
    btn.classList.add("btn-processing");
    btn.textContent = "Checking...";

    const response = await fetch("/api/forgot-password/get-question", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
    });
    const data = await response.json();

    // কাজ শেষ হয়ে গেছে (success হোক বা fail) - বাটন আগের অবস্থায় ফিরিয়ে আনছি
    btn.disabled = false;
    btn.classList.remove("btn-processing");
    btn.textContent = originalText;

    if (!data.success) {
        errorBox.textContent = data.message;
        errorBox.classList.remove("hidden");
        return;
    }

    currentProfessionalId = data.professional_id;

    if (data.blocked) {
        // ইতিমধ্যে ব্লক আছে -> কাউন্টডাউন দেখানো শুরু করি
        startLockoutCountdown(data.blocked_seconds);
        return;
    }

    // Security question box দেখানো হচ্ছে
    document.getElementById("security-question-text").textContent = data.security_question;
    document.getElementById("security-email-box").classList.add("hidden");
    document.getElementById("security-question-box").classList.remove("hidden");
});

// Security answer verify করা
document.getElementById("submit-answer-btn").addEventListener("click", async () => {
    const answer = document.getElementById("security-answer-input").value.trim();
    const errorBox = document.getElementById("security-error");
    errorBox.classList.add("hidden");

    // 🆕 প্রসেসিং অবস্থা
    const btn = document.getElementById("submit-answer-btn");
    const originalText = btn.textContent;
    btn.disabled = true;
    btn.classList.add("btn-processing");
    btn.textContent = "Verifying...";

    const response = await fetch("/api/forgot-password/verify-answer", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ professional_id: currentProfessionalId, answer }),
    });
    const data = await response.json();

    btn.disabled = false;
    btn.classList.remove("btn-processing");
    btn.textContent = originalText;

    if (data.success) {
        // ✅ উত্তর সঠিক -> reset password স্টেপে যাও
        showStep("reset-step");
        return;
    }

    if (data.blocked) {
        // ❌ এইমাত্র ব্লক হয়ে গেছে (৩ বারের ভুলের পর)
        startLockoutCountdown(data.seconds);
    } else {
        // ❌ ভুল উত্তর কিন্তু এখনো ব্লক হয়নি
        errorBox.textContent = "Wrong Answer! আবার চেষ্টা করো।";
        errorBox.classList.remove("hidden");
    }
});

// ---------- Lockout Countdown দেখানোর ফাংশন ----------
function startLockoutCountdown(seconds) {
    const errorBox = document.getElementById("security-error");
    document.getElementById("security-question-box").classList.add("hidden");
    document.getElementById("security-email-box").classList.add("hidden");
    errorBox.classList.remove("hidden");

    let remaining = seconds;
    const timer = setInterval(() => {
        errorBox.textContent = `অনেকবার ভুল উত্তর দেওয়া হয়েছে। অনুগ্রহ করে ${remaining} সেকেন্ড পর আবার চেষ্টা করো।`;
        remaining -= 1;

        if (remaining < 0) {
            clearInterval(timer);
            errorBox.classList.add("hidden");
            // সময় শেষ হলে আবার email box দেখিয়ে দিচ্ছি যাতে নতুন করে try করতে পারে
            document.getElementById("security-email-box").classList.remove("hidden");
        }
    }, 1000);
}

// =========================================================================
// STEP 3: নতুন পাসওয়ার্ড সেট করা
// =========================================================================
document.getElementById("reset-password-btn").addEventListener("click", async () => {
    const newPassword = document.getElementById("new-password-input").value;

    // 🆕 প্রসেসিং অবস্থা
    const btn = document.getElementById("reset-password-btn");
    const originalText = btn.textContent;
    btn.disabled = true;
    btn.classList.add("btn-processing");
    btn.textContent = "Saving...";

    const response = await fetch("/api/forgot-password/reset", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ professional_id: currentProfessionalId, new_password: newPassword }),
    });
    const data = await response.json();

    btn.disabled = false;
    btn.classList.remove("btn-processing");
    btn.textContent = originalText;

    if (data.success) {
        const successBox = document.getElementById("reset-success");
        successBox.textContent = "Password পরিবর্তন সফল হয়েছে! এখন লগইন করো।";
        successBox.classList.remove("hidden");
        setTimeout(() => showStep("login-step"), 1800);
    }
});
