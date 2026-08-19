/* =====================================================================
   admin.js  (🆕 নতুন ফাইল)
   ---------------------------
   Admin panel এর দুইটা পেজের (admin_login.html এবং admin.html) সব
   interactivity একটাই ফাইলে রাখা হয়েছে (অন্য পেজগুলোর মতো প্যাটার্ন
   অনুসরণ করে - একটা পেজ = একটা JS ফাইল)। কোন পেজে আছি সেটা বোঝার জন্য
   নির্দিষ্ট element আছে কিনা চেক করা হচ্ছে (যেমন #admin-login-btn শুধু
   admin_login.html এ থাকে, #professionals-table-body শুধু admin.html এ)।
   ===================================================================== */

// -------------------------------------------------------------------
// PART 1: ADMIN LOGIN পেজ (admin_login.html)
// -------------------------------------------------------------------
const adminLoginBtn = document.getElementById("admin-login-btn");
if (adminLoginBtn) {
    adminLoginBtn.addEventListener("click", async () => {
        const username = document.getElementById("admin-username").value.trim();
        const password = document.getElementById("admin-password").value;
        const errorBox = document.getElementById("admin-login-error");
        errorBox.classList.add("hidden");

        // প্রসেসিং অবস্থা
        const originalText = adminLoginBtn.textContent;
        adminLoginBtn.disabled = true;
        adminLoginBtn.classList.add("btn-processing");
        adminLoginBtn.textContent = "Logging in...";

        try {
            const response = await fetch("/api/admin/login", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ username, password }),
            });
            const data = await response.json();

            if (data.success) {
                window.location.href = data.redirect;
            } else {
                errorBox.textContent = data.message;
                errorBox.classList.remove("hidden");
                adminLoginBtn.disabled = false;
                adminLoginBtn.classList.remove("btn-processing");
                adminLoginBtn.textContent = originalText;
            }
        } catch (err) {
            errorBox.textContent = "কোনো সমস্যা হয়েছে, আবার চেষ্টা করো।";
            errorBox.classList.remove("hidden");
            adminLoginBtn.disabled = false;
            adminLoginBtn.classList.remove("btn-processing");
            adminLoginBtn.textContent = originalText;
        }
    });

    // Enter কী চাপলেও লগইন হবে
    document.getElementById("admin-password").addEventListener("keypress", (e) => {
        if (e.key === "Enter") adminLoginBtn.click();
    });
}

// -------------------------------------------------------------------
// PART 2: ADMIN DASHBOARD পেজ (admin.html)
// -------------------------------------------------------------------
const professionalsTableBody = document.getElementById("professionals-table-body");
if (professionalsTableBody) {

    // ---------------- Professional দের তালিকা লোড করা ----------------
    async function loadProfessionals() {
        // 🐛 BUG FIX: আগে এখানে try/catch ছিল না - কোনো কারণে request
        // fail করলে (network glitch, session expire ইত্যাদি) fetch()/
        // response.json() একটা exception ছুড়ত, যেটা কোথাও ধরা হতো না
        // (unhandled promise rejection) - ফলে console এ চুপচাপ error
        // লগ হতো কিন্তু ইউজার কিছুই বুঝতে পারত না, টেবিল খালি থেকে যেত।
        try {
            const response = await fetch("/api/admin/professionals");
            const data = await response.json();

            if (!response.ok) {
                console.error("Professionals লোড করা যায়নি:", data);
                return;
            }

            professionalsTableBody.innerHTML = "";  // আগের rows মুছে ফেলা হচ্ছে

        data.professionals.forEach((prof) => {
            const row = document.createElement("tr");
            // এখানে row তে ক্লিক করলে কোথাও যাওয়ার দরকার নেই, তাই hover
            // cursor pointer টা এই একটা row তে বন্ধ রাখা হলো (CSS তে
            // .student-table tbody tr এ ডিফল্ট cursor:pointer আছে যেটা
            // অন্য পেজগুলোতে ক্লিকযোগ্য rows এর জন্য দরকার)
            row.style.cursor = "default";
            row.innerHTML = `
                <td>${prof.professional_id}</td>
                <td>${prof.name}</td>
                <td>${prof.email}</td>
                <td>${prof.phone_number || "-"}</td>
                <td>${prof.gender || "-"}</td>
                <td>${prof.nid || "-"}</td>
                <td>${prof.blood_group || "-"}</td>
                <td>${prof.created_at}</td>
                <td><button class="admin-delete-btn" data-id="${prof.professional_id}" data-name="${prof.name}">Delete</button></td>
            `;
            professionalsTableBody.appendChild(row);
        });

        // প্রতিটা "Delete" বাটনে ক্লিক লিসেনার বসানো হচ্ছে (নতুন করে
        // রেন্ডার হওয়া প্রতিটা row এর জন্য আলাদা করে)।
        // 🐛 সতর্কতা: document.querySelectorAll() ব্যবহার করলে পেজের
        // অন্য কোথাও থাকা .admin-delete-btn (যেমন "Manage Student
        // Assessments" সেকশনের Delete বাটনগুলো, যেগুলোও একই CSS class
        // শেয়ার করে) ভুল করে ধরা পড়ে যেত এবং প্রতিবার loadProfessionals()
        // চললে সেগুলোতেও deleteProfessional() বসে যেত (double-handler)।
        // তাই এখানে শুধু professionalsTableBody এর ভেতরের বাটনগুলোতেই
        // scope করা হলো।
        professionalsTableBody.querySelectorAll(".admin-delete-btn").forEach((btn) => {
            btn.addEventListener("click", () => deleteProfessional(btn));
        });
        } catch (err) {
            console.error("Professionals লোড করার সময় সমস্যা হয়েছে:", err);
        }
    }

    // ---------------- একটা Professional ডিলিট করা ----------------
    async function deleteProfessional(btn) {
        const professionalId = btn.dataset.id;
        const professionalName = btn.dataset.name;

        const confirmed = confirm(`"${professionalName}" কে ডিলিট করতে চাও? এটা ফিরিয়ে আনা যাবে না।`);
        if (!confirmed) return;

        const originalText = btn.textContent;
        btn.disabled = true;
        btn.classList.add("btn-processing");
        btn.textContent = "Deleting...";

        try {
            const response = await fetch(`/api/admin/professionals/${professionalId}`, {
                method: "DELETE",
            });
            const data = await response.json();

            if (data.success) {
                // ডিলিট সফল হলে পুরো তালিকা আবার লোড করে নিচ্ছি
                loadProfessionals();
            } else {
                alert(data.message || "ডিলিট করা যায়নি।");
                btn.disabled = false;
                btn.classList.remove("btn-processing");
                btn.textContent = originalText;
            }
        } catch (err) {
            alert("কোনো সমস্যা হয়েছে, আবার চেষ্টা করো।");
            btn.disabled = false;
            btn.classList.remove("btn-processing");
            btn.textContent = originalText;
        }
    }

    // ---------------- নতুন Professional তৈরি করা ----------------
    document.getElementById("create-professional-btn").addEventListener("click", async () => {
        const errorBox = document.getElementById("create-professional-error");
        const successBox = document.getElementById("create-professional-success");
        errorBox.classList.add("hidden");
        successBox.classList.add("hidden");

        const payload = {
            name: document.getElementById("ap-name").value.trim(),
            email: document.getElementById("ap-email").value.trim(),
            phone_number: document.getElementById("ap-phone").value.trim() || null,
            gender: document.getElementById("ap-gender").value || null,
            nid: document.getElementById("ap-nid").value.trim() || null,
            blood_group: document.getElementById("ap-blood-group").value.trim() || null,
            password: document.getElementById("ap-password").value,
            security_question: document.getElementById("ap-security-question").value.trim(),
            security_answer: document.getElementById("ap-security-answer").value.trim(),
        };

        if (!payload.name || !payload.email || !payload.password) {
            errorBox.textContent = "Name, Email এবং Password অবশ্যই দিতে হবে।";
            errorBox.classList.remove("hidden");
            return;
        }

        const btn = document.getElementById("create-professional-btn");
        const originalText = btn.textContent;
        btn.disabled = true;
        btn.classList.add("btn-processing");
        btn.textContent = "Creating...";

        try {
            const response = await fetch("/api/admin/professionals", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            const data = await response.json();

            if (data.success) {
                successBox.textContent = "নতুন Professional account তৈরি হয়েছে!";
                successBox.classList.remove("hidden");
                // ফর্মটা খালি করে দেওয়া হচ্ছে পরের এন্ট্রির জন্য
                ["ap-name", "ap-email", "ap-phone", "ap-nid", "ap-blood-group",
                 "ap-password", "ap-security-question", "ap-security-answer"]
                    .forEach((id) => (document.getElementById(id).value = ""));
                document.getElementById("ap-gender").value = "Male";  // ডিফল্ট অপশনে ফিরিয়ে আনা
                loadProfessionals();  // তালিকা রিফ্রেশ করা হচ্ছে
            } else {
                errorBox.textContent = data.message;
                errorBox.classList.remove("hidden");
            }
        } catch (err) {
            errorBox.textContent = "কোনো সমস্যা হয়েছে, আবার চেষ্টা করো।";
            errorBox.classList.remove("hidden");
        } finally {
            btn.disabled = false;
            btn.classList.remove("btn-processing");
            btn.textContent = originalText;
        }
    });

    // পেজ লোড হওয়ার সাথে সাথেই প্রথমবার তালিকা লোড করা হচ্ছে
    loadProfessionals();
}

// =====================================================================
// 🆕 PART 3: MANAGE STUDENT ASSESSMENTS (admin.html এর নতুন সেকশন)
// ---------------------------------------------------------------------
// Student ID দিয়ে খুঁজে সেই student এর সব সম্পন্ন (Save করা) assessment
// দেখানো হয় (৩টা মডেলের ফলাফলসহ), আর প্রতিটার পাশে Delete বাটন থাকে।
// =====================================================================
const adminStudentSearchBtn = document.getElementById("admin-student-search-btn");
if (adminStudentSearchBtn) {

    let currentSearchedStudentId = null;  // Delete করার পর একই student এর জন্য আবার লোড করতে লাগবে

    async function loadStudentAssessmentsForAdmin(studentId) {
        const errorBox = document.getElementById("admin-student-search-error");
        const box = document.getElementById("admin-student-assessments-box");
        errorBox.classList.add("hidden");

        // =================================================================
        // 🐛 মূল BUG FIX: আগে এখানে try/catch ছিল না। fetch() বা
        // response.json() কোনো কারণে fail করলে (যেমন সার্ভার একটা 500
        // Internal Server Error - এর সাথে plain text/HTML রেসপন্স দিলে,
        // response.json() JSON parse করতে গিয়ে exception ছুড়ত) - সেই
        // exception টা কোথাও catch হতো না (কারণ এই async ফাংশনটা যেখান
        // থেকে কল হয় সেখানেও await/catch করা ছিল না)। ফলে এটা একটা
        // "unhandled promise rejection" হয়ে যেত - browser console এ
        // চুপচাপ লগ হতো, কিন্তু UI তে কিছুই দেখাত না - না error, না
        // ফলাফল। এটাই ছিল "সার্চ করলে কিছুই আসছে না" bug এর আসল কারণ।
        //
        // এখন পুরো fetch+parse+render try/catch দিয়ে মোড়ানো হলো, যাতে
        // যেকোনো সমস্যায় অন্তত errorBox এ একটা স্পষ্ট বার্তা দেখা যায়।
        // =================================================================
        try {
            const response = await fetch(`/api/admin/students/${encodeURIComponent(studentId)}/assessments`);
            const data = await response.json();

            if (!response.ok || !data.success) {
                // FastAPI এর HTTPException (যেমন 401 Admin login required)
                // "detail" key তে message পাঠায়, আর আমাদের নিজের endpoint
                // "message" key তে - তাই দুটোই চেক করা হচ্ছে
                errorBox.textContent = data.message || data.detail || "Student পাওয়া যায়নি।";
                errorBox.classList.remove("hidden");
                box.classList.add("hidden");
                return;
            }

            currentSearchedStudentId = studentId;

            document.getElementById("admin-student-assessments-title").textContent =
                `${data.student.name} (ID: ${data.student.student_id}) এর Assessment সমূহ`;

            const tbody = document.getElementById("admin-assessments-table-body");
            tbody.innerHTML = "";

            if (data.assessments.length === 0) {
                tbody.innerHTML = `<tr><td colspan="6" style="color:#9ca3af;">এই student এর এখনো কোনো assessment সম্পন্ন (Save) করা হয়নি।</td></tr>`;
            } else {
                data.assessments.forEach((a) => {
                    const row = document.createElement("tr");
                    const qCell = a.questionnaire_applicable ? (a.questionnaire_output || "-") : '<span style="color:#9ca3af;">নেওয়া হয়নি</span>';
                    const vCell = a.voice_applicable ? `${a.voice_output || "-"}${a.voice_risk ? ` (${a.voice_risk})` : ""}` : '<span style="color:#9ca3af;">নেওয়া হয়নি</span>';
                    const hCell = a.handwriting_applicable ? `${a.handwriting_output || "-"}${a.handwriting_risk ? ` (${a.handwriting_risk})` : ""}` : '<span style="color:#9ca3af;">নেওয়া হয়নি</span>';

                    row.innerHTML = `
                        <td>${a.created_at}</td>
                        <td>#${a.assessment_id}</td>
                        <td>${qCell}</td>
                        <td>${vCell}</td>
                        <td>${hCell}</td>
                        <td><button class="admin-delete-btn" data-assessment-id="${a.assessment_id}">Delete</button></td>
                    `;
                    tbody.appendChild(row);
                });

                // এই টেবিলের Delete বাটনগুলোতে আলাদা করে লিসেনার বসানো হচ্ছে
                // (উপরের Professional Delete থেকে আলাদা রাখা হলো, কারণ এটা
                // ভিন্ন endpoint কল করে - data-assessment-id দিয়ে বোঝা যাচ্ছে
                // কোনটা কোন ধরনের Delete বাটন)
                tbody.querySelectorAll(".admin-delete-btn[data-assessment-id]").forEach((btn) => {
                    btn.addEventListener("click", () => deleteAssessment(btn));
                });
            }

            box.classList.remove("hidden");
        } catch (err) {
            errorBox.textContent = "কোনো সমস্যা হয়েছে, আবার চেষ্টা করো। (দেখো: Console এ বিস্তারিত error আছে)";
            errorBox.classList.remove("hidden");
            box.classList.add("hidden");
            console.error("Student assessments লোড করার সময় সমস্যা:", err);
        }
    }

    async function deleteAssessment(btn) {
        const assessmentId = btn.dataset.assessmentId;

        const confirmed = confirm(`Assessment #${assessmentId} মুছে ফেলতে চাও? এটা ফিরিয়ে আনা যাবে না।`);
        if (!confirmed) return;

        const originalText = btn.textContent;
        btn.disabled = true;
        btn.classList.add("btn-processing");
        btn.textContent = "Deleting...";

        try {
            const response = await fetch(`/api/admin/assessments/${assessmentId}`, {
                method: "DELETE",
            });
            const data = await response.json();

            if (data.success) {
                // ডিলিট সফল হলে একই student এর জন্য তালিকা আবার লোড করা হচ্ছে
                loadStudentAssessmentsForAdmin(currentSearchedStudentId);
            } else {
                alert(data.message || "ডিলিট করা যায়নি।");
                btn.disabled = false;
                btn.classList.remove("btn-processing");
                btn.textContent = originalText;
            }
        } catch (err) {
            alert("কোনো সমস্যা হয়েছে, আবার চেষ্টা করো।");
            btn.disabled = false;
            btn.classList.remove("btn-processing");
            btn.textContent = originalText;
        }
    }

    adminStudentSearchBtn.addEventListener("click", () => {
        const studentId = document.getElementById("admin-student-search-id").value.trim();
        if (!studentId) return;
        loadStudentAssessmentsForAdmin(studentId);
    });

    // Enter কী চাপলেও সার্চ হবে
    document.getElementById("admin-student-search-id").addEventListener("keypress", (e) => {
        if (e.key === "Enter") adminStudentSearchBtn.click();
    });
}

// =====================================================================
// 🆕 PART 4: ALL STUDENTS (সার্চ ছাড়াই সব student দেখা)
// ---------------------------------------------------------------------
// admin.html এর "🎓 All Students" সেকশন - সব student এর তালিকা, প্রতিটা
// row এ "View Assessments" (উপরের Manage Student Assessments সেকশনে
// সেই student এর ID বসিয়ে assessment history দেখিয়ে দেয়) আর "Delete"
// (পুরো student + তার সব assessment ডিলিট করে) বাটন থাকে।
// =====================================================================
const adminStudentsTableBody = document.getElementById("admin-students-table-body");
if (adminStudentsTableBody) {

    async function loadAllStudents() {
        try {
            const response = await fetch("/api/admin/students");
            const data = await response.json();

            if (!response.ok || !data.success) {
                adminStudentsTableBody.innerHTML =
                    `<tr><td colspan="7" style="color:#dc2626;">${data.message || data.detail || "Student তালিকা লোড করা যায়নি।"}</td></tr>`;
                return;
            }

            adminStudentsTableBody.innerHTML = "";

            if (data.students.length === 0) {
                adminStudentsTableBody.innerHTML =
                    `<tr><td colspan="7" style="color:#9ca3af;">এখনো কোনো student যোগ করা হয়নি।</td></tr>`;
                return;
            }

            data.students.forEach((student) => {
                const row = document.createElement("tr");
                row.style.cursor = "default";  // পুরো row ক্লিকযোগ্য না, শুধু বাটন দুটো
                row.innerHTML = `
                    <td>${student.student_id}</td>
                    <td>${student.name}</td>
                    <td>${student.department || "-"}</td>
                    <td>${student.batch || "-"}</td>
                    <td>${student.semester || "-"}</td>
                    <td>${student.section || "-"}</td>
                    <td>
                        <button class="view-assessments-btn" data-student-id="${student.student_id}">View Assessments</button>
                        <button class="admin-delete-btn" data-student-id-delete="${student.student_id}" data-student-name="${student.name}">Delete</button>
                    </td>
                `;
                adminStudentsTableBody.appendChild(row);
            });

            // "View Assessments" - নিচের সার্চ বক্সে ID বসিয়ে সরাসরি সেই
            // student এর assessment history লোড করে দেয় (আলাদা করে টাইপ
            // করে সার্চ করতে হয় না)
            adminStudentsTableBody.querySelectorAll(".view-assessments-btn").forEach((btn) => {
                btn.addEventListener("click", () => {
                    const studentId = btn.dataset.studentId;
                    const searchInput = document.getElementById("admin-student-search-id");
                    if (searchInput) {
                        searchInput.value = studentId;
                        document.getElementById("admin-student-search-btn").click();
                        // ইউজারকে সরাসরি assessment history সেকশনে স্ক্রল করে দেখানো হচ্ছে
                        document.getElementById("admin-student-assessments-box")
                            .scrollIntoView({ behavior: "smooth", block: "start" });
                    }
                });
            });

            // "Delete" (student) - এই টেবিলের নিজস্ব delete বাটন, professionals
            // এর Delete থেকে আলাদা রাখতে data-student-id-delete attribute
            // ব্যবহার করা হলো (professional এর বাটনে data-id থাকে, এখানে
            // data-student-id-delete - তাই querySelectorAll("[data-id]")
            // দিয়ে ভুল করে ধরা পড়বে না)
            adminStudentsTableBody.querySelectorAll(".admin-delete-btn[data-student-id-delete]").forEach((btn) => {
                btn.addEventListener("click", () => deleteStudent(btn));
            });
        } catch (err) {
            adminStudentsTableBody.innerHTML =
                `<tr><td colspan="7" style="color:#dc2626;">কোনো সমস্যা হয়েছে, আবার চেষ্টা করো।</td></tr>`;
            console.error("All students লোড করার সময় সমস্যা:", err);
        }
    }

    async function deleteStudent(btn) {
        const studentId = btn.dataset.studentIdDelete;
        const studentName = btn.dataset.studentName;

        const confirmed = confirm(
            `"${studentName}" (ID: ${studentId}) কে ডিলিট করতে চাও? এর সাথে তার সব assessment ও ফলাফলও চিরতরে মুছে যাবে। এটা ফিরিয়ে আনা যাবে না।`
        );
        if (!confirmed) return;

        const originalText = btn.textContent;
        btn.disabled = true;
        btn.classList.add("btn-processing");
        btn.textContent = "Deleting...";

        try {
            const response = await fetch(`/api/admin/students/${encodeURIComponent(studentId)}`, {
                method: "DELETE",
            });
            const data = await response.json();

            if (data.success) {
                loadAllStudents();  // তালিকা রিফ্রেশ
            } else {
                alert(data.message || data.detail || "ডিলিট করা যায়নি।");
                btn.disabled = false;
                btn.classList.remove("btn-processing");
                btn.textContent = originalText;
            }
        } catch (err) {
            alert("কোনো সমস্যা হয়েছে, আবার চেষ্টা করো।");
            btn.disabled = false;
            btn.classList.remove("btn-processing");
            btn.textContent = originalText;
        }
    }

    loadAllStudents();
}
