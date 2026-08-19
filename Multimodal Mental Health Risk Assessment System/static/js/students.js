/* =====================================================================
   students.js
   ------------
   Students পেজের তালিকা লোড করা এবং Department/Semester/Section/Batch
   দিয়ে filter করার লজিক।
   ===================================================================== */

// ফিল্টার ড্রপডাউনগুলো থেকে বর্তমান মান নিয়ে API কে query parameter
// হিসেবে পাঠায় এবং টেবিল নতুন করে রেন্ডার করে
async function loadStudents() {
    const department = document.getElementById("filter-department").value;
    const semester = document.getElementById("filter-semester").value;
    const section = document.getElementById("filter-section").value;
    const batch = document.getElementById("filter-batch").value;

    // শুধু যেগুলোতে মান আছে সেগুলোই URL এ যোগ করি
    const params = new URLSearchParams();
    if (department) params.append("department", department);
    if (semester) params.append("semester", semester);
    if (section) params.append("section", section);
    if (batch) params.append("batch", batch);

    const response = await fetch(`/api/students?${params.toString()}`);
    const data = await response.json();

    const tbody = document.getElementById("students-table-body");
    tbody.innerHTML = "";  // আগের rows মুছে ফেলি

    data.students.forEach((student) => {
        const row = document.createElement("tr");
        row.innerHTML = `
            <td>${student.student_id}</td>
            <td>${student.name}</td>
            <td>${student.department || "-"}</td>
        `;
        // পুরো row ক্লিক করলে সেই student এর profile পেজে যাবে
        row.addEventListener("click", () => {
            window.location.href = `/student/${student.student_id}`;
        });
        tbody.appendChild(row);
    });

    // ফিল্টার ড্রপডাউনের option গুলো ডেটা থেকে dynamically পপুলেট করি
    // (প্রথমবার লোড হওয়ার সময়, unique মানগুলো বের করে বসিয়ে দিই)
    populateFilterOptions(data.students);
}

function populateFilterOptions(students) {
    // প্রতিটা ফিল্টারের জন্য আলাদা করে unique value বের করছি,
    // যাতে ড্রপডাউন duplicate হবে না বা খালি থাকবে না।
    const fields = [
        { id: "filter-department", key: "department" },
        { id: "filter-semester", key: "semester" },
        { id: "filter-section", key: "section" },
        { id: "filter-batch", key: "batch" },
    ];

    fields.forEach(({ id, key }) => {
        const select = document.getElementById(id);
        // যদি আগেই option বসানো হয়ে থাকে, দ্বিতীয়বার বসাব না (নাহলে duplicate হবে)
        if (select.dataset.populated === "true") return;

        const uniqueValues = [...new Set(students.map((s) => s[key]).filter(Boolean))];
        uniqueValues.forEach((value) => {
            const option = document.createElement("option");
            option.value = value;
            option.textContent = value;
            select.appendChild(option);
        });
        select.dataset.populated = "true";
    });
}

// ৪টা ফিল্টার ড্রপডাউনের যেকোনো একটা বদলালেই আবার লোড হবে
["filter-department", "filter-semester", "filter-section", "filter-batch"].forEach((id) => {
    document.getElementById(id).addEventListener("change", loadStudents);
});

// পেজ লোড হওয়ার সাথে সাথেই প্রথমবার সব student লোড করি
loadStudents();
