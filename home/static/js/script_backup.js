// =========================================================
// FocusFrame — Firebase + Page Scripts
// =========================================================


// =========================================================
// FIREBASE CONFIGURATION
// =========================================================

const firebaseConfig = {

    apiKey: "AIzaSyB0a2RkXc3Rj24pPEfQzoniZWtQM1iC-1o",

    authDomain:
        "focusframe-123b6.firebaseapp.com",

    projectId:
        "focusframe-123b6",

    storageBucket:
        "focusframe-123b6.firebasestorage.app",

    messagingSenderId:
        "620956140159",

    appId:
        "1:620956140159:web:bc30ca87387b48e226b54a",

    measurementId:
        "G-5M41Z6K15T"
};


// =========================================================
// INITIALIZE FIREBASE
// =========================================================

if (!firebase.apps.length) {

    firebase.initializeApp(firebaseConfig);

}


const auth = firebase.auth();

const database = firebase.database();


// =========================================================
// HOME PAGE
// =========================================================

document.addEventListener(
    "DOMContentLoaded",
    function () {

        document
            .querySelectorAll('a[href^="#"]')
            .forEach(function (link) {

                link.addEventListener(
                    "click",
                    function (e) {

                        const target =
                            document.querySelector(
                                link.getAttribute("href")
                            );

                        if (target) {

                            e.preventDefault();

                            target.scrollIntoView({
                                behavior: "smooth",
                                block: "start"
                            });

                        }

                    }
                );

            });

    }
);


// =========================================================
// LOGIN PAGE
// =========================================================

document.addEventListener(
    "DOMContentLoaded",
    function () {

        const form =
            document.getElementById("loginForm");


        // Not login page
        if (!form) {
            return;
        }


        const roleTabs =
            document.querySelectorAll(".role-tab");


        const labelRoles =
            document.querySelectorAll(".label-role");


        const idField =
            document.getElementById("loginId");


        const pwInput =
            document.getElementById("loginPassword");


        const pwToggle =
            document.getElementById("pwToggle");


        const note =
            document.getElementById("formNote");


        let selectedRole = "student";


        // =====================================================
        // SET ROLE
        // =====================================================

        function setRole(role) {

            selectedRole = role;


            roleTabs.forEach(function (tab) {

                const active =
                    tab.dataset.role === role;


                tab.classList.toggle(
                    "is-active",
                    active
                );


                tab.setAttribute(
                    "aria-selected",
                    active ? "true" : "false"
                );

            });


            labelRoles.forEach(function (label) {

                label.classList.toggle(
                    "is-current",
                    label.classList.contains(
                        "label-" + role
                    )
                );

            });

        }


        roleTabs.forEach(function (tab) {

            tab.addEventListener(
                "click",
                function () {

                    setRole(
                        tab.dataset.role
                    );

                }
            );

        });


        setRole("student");


        // =====================================================
        // PASSWORD SHOW/HIDE
        // =====================================================

        if (pwToggle && pwInput) {

            pwToggle.addEventListener(
                "click",
                function () {

                    const isPassword =
                        pwInput.type === "password";


                    pwInput.type =
                        isPassword
                            ? "text"
                            : "password";


                    pwToggle.textContent =
                        isPassword
                            ? "Hide"
                            : "Show";

                }
            );

        }


        // =====================================================
        // LOGIN
        // =====================================================

        form.addEventListener(
            "submit",
            function (e) {

                e.preventDefault();


                const email =
                    idField.value.trim();


                const password =
                    pwInput.value;


                if (!email || !password) {

                    note.textContent =
                        "Please enter your email and password.";

                    note.classList.add(
                        "is-error"
                    );

                    return;

                }


                note.classList.remove(
                    "is-error"
                );


                note.textContent =
                    "Signing in...";


                // =================================================
                // FIREBASE LOGIN
                // =================================================

                auth.signInWithEmailAndPassword(
                    email,
                    password
                )

                .then(function (userCredential) {

                    const user =
                        userCredential.user;


                    console.log(
                        "Firebase login successful:",
                        user.uid
                    );


                    // Get user role
                    return database
                        .ref(
                            "users/" + user.uid
                        )
                        .once("value");

                })


                .then(function (snapshot) {

                    const userData =
                        snapshot.val();


                    let role =
                        selectedRole;


                    if (
                        userData &&
                        userData.role
                    ) {

                        role =
                            userData.role;

                    }


                    // =================================================
                    // STUDENT
                    // =================================================

                    if (role === "student") {

                        note.textContent =
                            "Login successful!";


                        setTimeout(
                            function () {

                                window.location.href ="/student/";

                            },
                            700
                        );


                        return;

                    }


                    // =================================================
                    // TEACHER
                    // =================================================

                    if (role === "teacher") {

                        note.textContent =
                            "Checking teacher approval...";


                        return fetch(
                            "/teacher-status/?email=" +
                            encodeURIComponent(
                                idField.value.trim()
                            )
                        )

                        .then(function (response) {

                            return response.json();

                        })

                        .then(function (statusData) {


                            // -------------------------------
                            // PENDING
                            // -------------------------------

                            if (
                                statusData.status ===
                                "Pending"
                            ) {

                                throw new Error(
                                    "PENDING_APPROVAL"
                                );

                            }


                            // -------------------------------
                            // REJECTED
                            // -------------------------------

                            if (
                                statusData.status ===
                                "Rejected"
                            ) {

                                throw new Error(
                                    "REJECTED_TEACHER"
                                );

                            }


                            // -------------------------------
                            // APPROVED
                            // -------------------------------

                            if (
                                statusData.status ===
                                "Approved"
                            ) {

                                note.classList.remove(
                                    "is-error"
                                );

                                note.textContent =
                                    "Teacher approved!";


                                setTimeout(
                                    function () {

                                        window.location.href =
                                            "/teacher/";

                                    },
                                    700
                                );


                                return;

                            }


                            // -------------------------------
                            // NOT FOUND
                            // -------------------------------

                            throw new Error(
                                "TEACHER_NOT_FOUND"
                            );

                        });

                    }


                    // =================================================
                    // ADMIN
                    // =================================================

                    if (role === "admin") {

                        note.textContent =
                            "Login successful!";


                        setTimeout(
                            function () {

                                window.location.href =
                                    "/admin/";

                            },
                            700
                        );

                    }

                })


                // =====================================================
                // LOGIN ERROR
                // =====================================================

                .catch(function (error) {

                    console.error(
                        "Firebase login error:",
                        error
                    );


                    note.classList.add(
                        "is-error"
                    );


                    if (
                        error.message ===
                        "PENDING_APPROVAL"
                    ) {

                        note.textContent =
                            "Your teacher account is waiting for admin approval.";

                    }

                    else if (
                        error.message ===
                        "REJECTED_TEACHER"
                    ) {

                        note.textContent =
                            "Your teacher registration was rejected by the admin.";

                    }

                    else if (
                        error.message ===
                        "TEACHER_NOT_FOUND"
                    ) {

                        note.textContent =
                            "Teacher approval request not found.";

                    }

                    else if (
                        error.code ===
                        "auth/invalid-credential"
                        ||
                        error.code ===
                        "auth/wrong-password"
                    ) {

                        note.textContent =
                            "Invalid email or password.";

                    }

                    else if (
                        error.code ===
                        "auth/user-not-found"
                    ) {

                        note.textContent =
                            "No account found with this email.";

                    }

                    else {

                        note.textContent =
                            error.message;

                    }

                });

            }
        );

    }
);


// =========================================================
// REGISTER PAGE
// =========================================================

document.addEventListener(
    "DOMContentLoaded",
    function () {

        const form =
            document.getElementById("registerForm");


        // Not register page
        if (!form) {
            return;
        }


        // =====================================================
        // ELEMENTS
        // =====================================================

        const roleTabs =
            document.querySelectorAll(".role-tab");


        const studentFields =
            document.querySelector(
                ".role-fields-student"
            );


        const teacherFields =
            document.querySelector(
                ".role-fields-teacher"
            );


        const selectedRoleInput =
            document.getElementById(
                "selectedRole"
            );


        const fullName =
            document.getElementById(
                "regName"
            );


        const regNumber =
            document.getElementById(
                "regNumber"
            );


        const classBatch =
            document.getElementById(
                "classBatch"
            );


        const deviceId =
            document.getElementById(
                "deviceId"
            );


        const employeeId =
            document.getElementById(
                "employeeId"
            );


        const department =
            document.getElementById(
                "department"
            );


        const email =
            document.getElementById(
                "regEmail"
            );


        const password =
            document.getElementById(
                "regPassword"
            );


        const confirmPassword =
            document.getElementById(
                "confirmPassword"
            );


        const terms =
            document.getElementById(
                "agreeTerms"
            );


        const termsError =
            document.getElementById(
                "termsError"
            );


        const note =
            document.getElementById(
                "formNote"
            );


        let selectedRole =
            "student";


        // =====================================================
        // SET ROLE
        // =====================================================

        function setRole(role) {

            selectedRole =
                role;


            // Update hidden input
            if (selectedRoleInput) {

                selectedRoleInput.value =
                    role;

            }


            // Update tabs
            roleTabs.forEach(
                function (tab) {

                    const active =
                        tab.dataset.role === role;


                    tab.classList.toggle(
                        "is-active",
                        active
                    );


                    tab.setAttribute(
                        "aria-selected",
                        active
                            ? "true"
                            : "false"
                    );

                }
            );


            // Show/hide fields
            if (role === "student") {

                studentFields.hidden =
                    false;

                teacherFields.hidden =
                    true;

            }


            if (role === "teacher") {

                studentFields.hidden =
                    true;

                teacherFields.hidden =
                    false;

            }

        }


        // =====================================================
        // ROLE BUTTONS
        // =====================================================

        roleTabs.forEach(
            function (tab) {

                tab.addEventListener(
                    "click",
                    function () {

                        setRole(
                            tab.dataset.role
                        );

                    }
                );

            }
        );


        setRole("student");


        // =====================================================
        // REGISTER
        // =====================================================

        form.addEventListener(
            "submit",
            function (e) {

                e.preventDefault();


                note.classList.remove(
                    "is-error"
                );


                // =================================================
                // BASIC VALIDATION
                // =================================================

                if (!fullName.value.trim()) {

                    note.textContent =
                        "Please enter your full name.";

                    note.classList.add(
                        "is-error"
                    );

                    return;

                }


                if (!email.value.trim()) {

                    note.textContent =
                        "Please enter your email.";

                    note.classList.add(
                        "is-error"
                    );

                    return;

                }


                if (
                    password.value.length < 8
                ) {

                    note.textContent =
                        "Password must be at least 8 characters.";

                    note.classList.add(
                        "is-error"
                    );

                    return;

                }


                if (
                    password.value !==
                    confirmPassword.value
                ) {

                    note.textContent =
                        "Passwords don't match.";

                    note.classList.add(
                        "is-error"
                    );

                    return;

                }


                if (!terms.checked) {

                    termsError.classList.add(
                        "is-visible"
                    );

                    note.textContent =
                        "Please accept the monitoring terms.";

                    note.classList.add(
                        "is-error"
                    );

                    return;

                }


                termsError.classList.remove(
                    "is-visible"
                );


                // =================================================
                // STUDENT VALIDATION
                // =================================================

                if (
                    selectedRole ===
                    "student"
                ) {

                    if (
                        !regNumber.value.trim()
                    ) {

                        note.textContent =
                            "Please enter your register number.";

                        note.classList.add(
                            "is-error"
                        );

                        return;

                    }


                    if (
                        !classBatch.value.trim()
                    ) {

                        note.textContent =
                            "Please enter your class / batch.";

                        note.classList.add(
                            "is-error"
                        );

                        return;

                    }

                }


                // =================================================
                // TEACHER VALIDATION
                // =================================================

                if (
                    selectedRole ===
                    "teacher"
                ) {

                    if (
                        !employeeId.value.trim()
                    ) {

                        note.textContent =
                            "Please enter your employee ID.";

                        note.classList.add(
                            "is-error"
                        );

                        return;

                    }


                    if (
                        !department.value.trim()
                    ) {

                        note.textContent =
                            "Please enter your department.";

                        note.classList.add(
                            "is-error"
                        );

                        return;

                    }

                }


                // =================================================
                // START REGISTRATION
                // =================================================

                note.textContent =
                    "Creating account...";


                console.log(
                    "Starting Firebase registration..."
                );


                // =================================================
                // CREATE FIREBASE ACCOUNT
                // =================================================

                auth.createUserWithEmailAndPassword(
                    email.value.trim(),
                    password.value
                )


                .then(
                    function (userCredential) {

                        const user =
                            userCredential.user;


                        console.log(
                            "Firebase account created:",
                            user.uid
                        );


                        // =================================================
                        // USER DATA
                        // =================================================

                        const userData = {

                            fullName:
                                fullName.value.trim(),

                            email:
                                email.value.trim(),

                            role:
                                selectedRole,

                            createdAt:
                                new Date().toISOString()

                        };


                        // =================================================
                        // STUDENT DATA
                        // =================================================

                        if (
                            selectedRole ===
                            "student"
                        ) {

                            userData.registerNumber =
                                regNumber.value.trim();


                            userData.classBatch =
                                classBatch.value.trim();


                            userData.deviceId =
                                deviceId.value.trim();

                        }


                        // =================================================
                        // TEACHER DATA
                        // =================================================

                        if (
                            selectedRole ===
                            "teacher"
                        ) {

                            userData.employeeId =
                                employeeId.value.trim();


                            userData.department =
                                department.value.trim();


                            // Initial approval state
                            userData.approvalStatus =
                                "Pending";

                        }


                        // =================================================
                        // SAVE TO FIREBASE
                        // =================================================

                        return database
                            .ref(
                                "users/" +
                                user.uid
                            )
                            .set(userData);

                    }
                )


                // =====================================================
                // AFTER FIREBASE SAVE
                // =====================================================

                .then(
                    function () {

                        console.log(
                            "User information saved to Firebase."
                        );


                        // =================================================
                        // TEACHER → SEND REQUEST TO DJANGO
                        // =================================================

                        if (
                            selectedRole ===
                            "teacher"
                        ) {


                            const csrfToken =
                                document.querySelector(
                                    "[name=csrfmiddlewaretoken]"
                                ).value;


                            const formData =
                                new FormData();


                            formData.append(
                                "role",
                                "teacher"
                            );


                            formData.append(
                                "fullName",
                                fullName.value.trim()
                            );


                            formData.append(
                                "employeeId",
                                employeeId.value.trim()
                            );


                            formData.append(
                                "department",
                                department.value.trim()
                            );


                            formData.append(
                                "regEmail",
                                email.value.trim()
                            );


                            return fetch(
                                "/register/",
                                {

                                    method: "POST",

                                    headers: {
                                        "X-CSRFToken":
                                            csrfToken
                                    },

                                    body:
                                        formData

                                }
                            )

                            .then(
                                function (
                                    response
                                ) {

                                    if (
                                        !response.ok
                                    ) {

                                        throw new Error(
                                            "Could not submit teacher approval request."
                                        );

                                    }


                                    return response.json();

                                }
                            );

                        }


                        return null;

                    }
                )


                // =====================================================
                // SUCCESS
                // =====================================================

                .then(
                    function () {

                        note.classList.remove(
                            "is-error"
                        );


                        if (
                            selectedRole ===
                            "teacher"
                        ) {

                            note.textContent =
                                "Teacher account created. Waiting for admin approval.";

                        }

                        else {

                            note.textContent =
                                "Account created successfully!";

                        }


                        setTimeout(
                            function () {

                                window.location.href =
                                    "/login/";

                            },
                            1800
                        );

                    }
                )


                // =====================================================
                // ERROR
                // =====================================================

                .catch(
                    function (error) {

                        console.error(
                            "Registration error:",
                            error
                        );


                        note.classList.add(
                            "is-error"
                        );


                        if (
                            error.code ===
                            "auth/email-already-in-use"
                        ) {

                            note.textContent =
                                "This email is already registered.";

                        }

                        else if (
                            error.code ===
                            "auth/invalid-email"
                        ) {

                            note.textContent =
                                "Please enter a valid email address.";

                        }

                        else if (
                            error.code ===
                            "auth/weak-password"
                        ) {

                            note.textContent =
                                "Password is too weak.";

                        }

                        else {

                            note.textContent =
                                "Registration failed: " +
                                error.message;

                        }

                    }
                );

            }
        );


        // =====================================================
        // REMOVE TERMS ERROR
        // =====================================================

        if (terms) {

            terms.addEventListener(
                "change",
                function () {

                    if (terms.checked) {

                        termsError.classList.remove(
                            "is-visible"
                        );


                        note.textContent = "";

                    }

                }
            );

        }

    }
);