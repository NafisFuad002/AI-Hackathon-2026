/* =====================================================================
   student_profile.js  (🆕 নতুন ফাইল)
   ------------------------------------
   Student profile পেজে "+ New Assessment for this Student" বাটনে ক্লিক
   করলে আগে সরাসরি /new-assessment এ (Existing/New Student বাছাইয়ের
   choice-page এ) নিয়ে যেত - যেটা অপ্রয়োজনীয় ছিল, কারণ আমরা already
   জানি এই assessment টা কোন student এর জন্য (এই পেজেই student এর
   প্রোফাইলে আছি)।

   তাই এখন এই বাটনে ক্লিক করলে সরাসরি /api/assessments/start কল করে এই
   student এর জন্য একটা নতুন assessment session শুরু করে দেওয়া হচ্ছে,
   এবং সরাসরি assessment পেজে (/assessment/{id}) পাঠিয়ে দেওয়া হচ্ছে -
   মাঝখানের choice/search ধাপ পুরোপুরি বাদ।
   ===================================================================== */

// পেজ লোড হওয়ার সাথে সাথেই বাটনের আসল টেক্সট একবার save করে রাখা হচ্ছে
// (dataset.originalText এ) - এতে click আর নিচের pageshow (bfcache fix)
// দুই জায়গাতেই একই, ঠিক আসল টেক্সট ব্যবহার হবে
const newAssessmentBtn = document.getElementById("new-assessment-for-student-btn");
if (newAssessmentBtn) {
    newAssessmentBtn.dataset.originalText = newAssessmentBtn.textContent.trim();
}

document.getElementById("new-assessment-for-student-btn").addEventListener("click", async (e) => {
    // href="#" যাতে পেজ রিলোড/স্ক্রল না করে, তাই preventDefault করা হচ্ছে
    e.preventDefault();

    const btn = e.currentTarget;
    const studentId = btn.dataset.studentId;  // HTML এ data-student-id attribute থেকে আসছে

    // প্রসেসিং অবস্থায় বাটনের টেক্সট বদলে "Processing..." দেখানো হচ্ছে,
    // এবং pointer-events বন্ধ করে দেওয়া হচ্ছে যাতে ডাবল-ক্লিক করে দুইটা
    // assessment session তৈরি হয়ে না যায়
    const originalText = btn.dataset.originalText || btn.textContent;
    btn.textContent = "Processing...";
    btn.classList.add("btn-processing");

    const formData = new FormData();
    formData.append("student_id", studentId);

    try {
        const response = await fetch("/api/assessments/start", {
            method: "POST",
            body: formData,
        });
        const data = await response.json();

        if (data.success) {
            // নতুন assessment তৈরি হয়ে গেছে -> সরাসরি সেই assessment পেজে পাঠিয়ে দিচ্ছি
            window.location.href = `/assessment/${data.assessment_id}`;
        } else {
            // ব্যর্থ হলে বাটন আগের অবস্থায় ফিরিয়ে এনে ইউজারকে জানানো হচ্ছে
            btn.textContent = originalText;
            btn.classList.remove("btn-processing");
            alert("Assessment শুরু করা যায়নি, আবার চেষ্টা করো।");
        }
    } catch (err) {
        btn.textContent = originalText;
        btn.classList.remove("btn-processing");
        alert("কোনো সমস্যা হয়েছে, আবার চেষ্টা করো।");
    }
});

// =====================================================================
// 🐛 BUG FIX: "New Assessment" বাটনে ক্লিক করার পর assessment পেজে চলে
// যাওয়া হতো (window.location.href), তখন বাটনটা "Processing..." অবস্থাতেই
// থেকে যেত (কারণ ওই পেজেই তো আর ফেরা হচ্ছিল না, তাই কখনো reset করা হয়নি)।
//
// সমস্যা হলো - ইউজার যদি তারপর ব্রাউজারের Back বাটনে চাপে, তাহলে ব্রাউজার
// (Chrome/Firefox/Safari) নতুন করে পেজ লোড না করে "bfcache" (back-forward
// cache) থেকে ঠিক আগের DOM অবস্থাটাই ফিরিয়ে দেয় - অর্থাৎ বাটনটা তখনও
// "Processing..." লেখা আর ক্লিক-অযোগ্য অবস্থাতেই দেখাচ্ছিল, যদিও আসলে
// নতুন কিছু প্রসেস হচ্ছে না।
//
// ✅ FIX: browser এর "pageshow" ইভেন্ট শোনা হচ্ছে, যেটা bfcache থেকে
// পেজ ফিরে এলে event.persisted = true নিয়ে ফায়ার হয়। তখন বাটনটাকে
// জোর করে আবার আগের (normal) অবস্থায় ফিরিয়ে আনা হচ্ছে।
// =====================================================================
window.addEventListener("pageshow", (event) => {
    if (event.persisted) {
        const btn = document.getElementById("new-assessment-for-student-btn");
        if (btn) {
            btn.textContent = btn.dataset.originalText || "+ New Assessment for this Student";
            btn.classList.remove("btn-processing");
        }
    }
});
