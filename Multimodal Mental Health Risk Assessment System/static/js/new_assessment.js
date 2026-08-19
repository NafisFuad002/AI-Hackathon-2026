/* =====================================================================
   new_assessment.js
   ------------------
   New Assessment পেজের লজিক। ৩টা ধাপ:
     1) choice-step    -> New Student না Existing Student বাছাই
     2) existing-step   -> Student ID দিয়ে খোঁজা
     3) new-student-step -> নতুন student এর তথ্য ফর্ম
   যেকোনো একটা পথ শেষে assessment session শুরু হয়ে assessment পেজে চলে যায়।
   ===================================================================== */

function showOnly(stepId) {
    ["choice-step", "existing-step", "new-student-step"].forEach((id) => {
        document.getElementById(id).classList.toggle("hidden", id !== stepId);
    });
}

document.getElementById("existing-student-card").addEventListener("click", () => {
    showOnly("existing-step");
});

document.getElementById("new-student-card").addEventListener("click", () => {
    showOnly("new-student-step");
});

// -------------------------------------------------------------------
// EXISTING STUDENT সার্চ
// -------------------------------------------------------------------
document.getElementById("existing-search-btn").addEventListener("click", async () => {
    const studentId = document.getElementById("existing-student-id").value.trim();
    const errorBox = document.getElementById("existing-error");
    errorBox.classList.add("hidden");

    // 🆕 প্রসেসিং অবস্থা
    const btn = document.getElementById("existing-search-btn");
    const originalText = btn.textContent;
    btn.disabled = true;
    btn.classList.add("btn-processing");
    btn.textContent = "Searching...";

    const response = await fetch(`/api/students/search/${studentId}`);

    btn.disabled = false;
    btn.classList.remove("btn-processing");
    btn.textContent = originalText;

    if (!response.ok) {
        errorBox.classList.remove("hidden");
        document.getElementById("found-student-box").classList.add("hidden");
        return;
    }

    const data = await response.json();
    const student = data.student;

    const card = document.getElementById("found-student-card");
    card.innerHTML = `
        <strong>${student.name}</strong> (ID: ${student.student_id})<br>
        <span style="font-size:13px;color:#6b7280;">Section: ${student.section || "-"}</span>
        <p style="margin-top:10px;color:#4f46e5;font-weight:600;">Click to start assessment →</p>
    `;
    // এই student এর ওপর ক্লিক করলেই নতুন assessment তথ্য না নিয়ে সরাসরি শুরু হয়ে যাবে
    card.onclick = () => startAssessment(student.student_id);

    document.getElementById("found-student-box").classList.remove("hidden");
});

// -------------------------------------------------------------------
// NEW STUDENT ফর্ম সাবমিট
// -------------------------------------------------------------------
document.getElementById("save-new-student-btn").addEventListener("click", async () => {
    const errorBox = document.getElementById("new-student-error");
    errorBox.classList.add("hidden");

    const btn = document.getElementById("save-new-student-btn");

    const studentData = {
        student_id: document.getElementById("ns-student-id").value.trim(),
        name: document.getElementById("ns-name").value.trim(),
        email: document.getElementById("ns-email").value.trim(),
        phone_number: document.getElementById("ns-phone").value.trim(),
        department: document.getElementById("ns-department").value.trim(),
        batch: document.getElementById("ns-batch").value.trim(),
        semester: document.getElementById("ns-semester").value.trim(),
        section: document.getElementById("ns-section").value.trim(),
        blood_group: document.getElementById("ns-blood-group").value.trim(),
        date_of_birth: document.getElementById("ns-dob").value,
        age: parseInt(document.getElementById("ns-age").value) || null,
        gender: document.getElementById("ns-gender").value,
    };

    if (!studentData.student_id || !studentData.name) {
        errorBox.textContent = "Student ID এবং Name অবশ্যই দিতে হবে।";
        errorBox.classList.remove("hidden");
        return;
    }

    // 🆕 প্রসেসিং অবস্থা - এই বাটন সেভ করার পাশাপাশি assessment ও শুরু
    // করে, তাই টেক্সট একটু জেনারেল রাখা হলো
    const originalText = btn.textContent;
    btn.disabled = true;
    btn.classList.add("btn-processing");
    btn.textContent = "Processing...";

    const response = await fetch("/api/students", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(studentData),
    });
    const data = await response.json();

    if (!data.success) {
        errorBox.textContent = data.message;
        errorBox.classList.remove("hidden");
        btn.disabled = false;
        btn.classList.remove("btn-processing");
        btn.textContent = originalText;
        return;
    }

    // Student সেভ হয়ে গেছে -> এখন assessment শুরু করি
    // (এখান থেকেই startAssessment() পেজ redirect করে দেবে, তাই বাটন
    // আর ফিরিয়ে আনার দরকার নেই)
    startAssessment(studentData.student_id);
});

// -------------------------------------------------------------------
// একটা assessment session শুরু করে assessment পেজে redirect করে
// (দুই পথেই - Existing ও New Student - শেষে এই একই ফাংশন কল হয়)
// -------------------------------------------------------------------
async function startAssessment(studentId) {
    // এই ফাংশনটা দুই জায়গা থেকে কল হয় - "found student" কার্ডে ক্লিক
    // করলে, আর নতুন student ফর্ম সেভ করার পর। কার্ড থেকে কল হলে যেন
    // ইউজার বুঝতে পারে কিছু একটা হচ্ছে, তাই কার্ডটা থাকলে তার ভেতরে
    // একটা ছোট "প্রসেসিং" ইঙ্গিত দেখানো হচ্ছে।
    const card = document.getElementById("found-student-card");
    if (card) {
        card.style.opacity = "0.6";
        card.style.pointerEvents = "none";
    }

    try {
        const formData = new FormData();
        formData.append("student_id", studentId);

        const response = await fetch("/api/assessments/start", {
            method: "POST",
            body: formData,
        });
        const data = await response.json();

        if (data.success) {
            window.location.href = `/assessment/${data.assessment_id}`;
        } else if (card) {
            card.style.opacity = "1";
            card.style.pointerEvents = "auto";
            alert("Assessment শুরু করা যায়নি, আবার চেষ্টা করো।");
        }
    } catch (err) {
        if (card) {
            card.style.opacity = "1";
            card.style.pointerEvents = "auto";
        }
        alert("কোনো সমস্যা হয়েছে, আবার চেষ্টা করো।");
    }
}
