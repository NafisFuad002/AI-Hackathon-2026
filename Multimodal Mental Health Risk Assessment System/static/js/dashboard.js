/* =====================================================================
   dashboard.js
   -------------
   Dashboard এর Student ID search বক্সের জন্য। Search চাপলে API কল করে
   student খুঁজে পাওয়া গেলে সরাসরি সেই student এর profile পেজে পাঠিয়ে দেয়।
   ===================================================================== */

document.getElementById("search-btn").addEventListener("click", async () => {
    const studentId = document.getElementById("search-student-id").value.trim();
    const errorBox = document.getElementById("search-error");
    const btn = document.getElementById("search-btn");

    if (!studentId) return;

    // 🆕 প্রসেসিং অবস্থা - খোঁজা চলাকালীন বাটনে "Searching..." দেখানো হচ্ছে
    const originalText = btn.textContent;
    btn.disabled = true;
    btn.classList.add("btn-processing");
    btn.textContent = "Searching...";
    errorBox.classList.add("hidden");

    try {
        const response = await fetch(`/api/students/search/${studentId}`);

        if (response.ok) {
            // Student পাওয়া গেছে -> তার প্রোফাইল/history পেজে নিয়ে যাও
            window.location.href = `/student/${studentId}`;
            // পেজ বদলে যাচ্ছে তাই বাটন ফিরিয়ে আনার দরকার নেই
        } else {
            errorBox.classList.remove("hidden");
            btn.disabled = false;
            btn.classList.remove("btn-processing");
            btn.textContent = originalText;
        }
    } catch (err) {
        errorBox.classList.remove("hidden");
        btn.disabled = false;
        btn.classList.remove("btn-processing");
        btn.textContent = originalText;
    }
});

// Enter কী চাপলেও যেন সার্চ হয়
document.getElementById("search-student-id").addEventListener("keypress", (e) => {
    if (e.key === "Enter") document.getElementById("search-btn").click();
});
