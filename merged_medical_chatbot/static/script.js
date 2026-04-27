// ---------- LOGIN PAGE FUNCTIONS ----------

async function loginUser() {
    const usernameEl = document.getElementById("username");
    const passwordEl = document.getElementById("password");
    const authMessage = document.getElementById("authMessage");

    const username = usernameEl ? usernameEl.value.trim() : "";
    const password = passwordEl ? passwordEl.value.trim() : "";

    if (!username || !password) {
        if (authMessage) authMessage.innerText = "Please enter username and password";
        return;
    }

    try {
        const formData = new FormData();
        formData.append("username", username);
        formData.append("password", password);

        const response = await fetch("/login", {
            method: "POST",
            body: formData
        });

        const data = await response.json();

        if (data.message === "Login successful") {
            window.location.href = "/chat";
        } else {
            if (authMessage) authMessage.innerText = data.message || "Login failed";
        }
    } catch (error) {
        console.error("Login error:", error);
        if (authMessage) authMessage.innerText = "Something went wrong";
    }
}

async function signupUser() {
    const usernameEl = document.getElementById("username");
    const passwordEl = document.getElementById("password");
    const authMessage = document.getElementById("authMessage");

    const username = usernameEl ? usernameEl.value.trim() : "";
    const password = passwordEl ? passwordEl.value.trim() : "";

    if (!username || !password) {
        if (authMessage) authMessage.innerText = "Please enter username and password";
        return;
    }

    try {
        const formData = new FormData();
        formData.append("username", username);
        formData.append("password", password);

        const response = await fetch("/signup", {
            method: "POST",
            body: formData
        });

        const data = await response.json();

        if (data.message === "Signup successful") {
            if (authMessage) authMessage.innerText = "Account created successfully. Please login.";
        } else {
            if (authMessage) authMessage.innerText = data.message || "Signup failed";
        }
    } catch (error) {
        console.error("Signup error:", error);
        if (authMessage) authMessage.innerText = "Something went wrong";
    }
}

function continueAsGuest() {
    window.location.href = "/guest";
}

// old-name compatibility
function login() {
    loginUser();
}

function signup() {
    signupUser();
}

function guestLogin() {
    continueAsGuest();
}

// ---------- CHAT PAGE FUNCTIONS ----------

let selectedImageFile = null;
let chatHistory = [];

function openFilePicker() {
    const imageInput = document.getElementById("imageInput");
    if (imageInput) imageInput.click();
}

function previewImage(event) {
    const file = event.target.files[0];
    if (!file) return;

    selectedImageFile = file;

    const fileName = document.getElementById("fileName");
    const preview = document.getElementById("preview");

    if (fileName) fileName.innerText = file.name;

    if (preview) {
        preview.src = URL.createObjectURL(file);
        preview.style.display = "block";
    }
}

function fillQuestion(text) {
    const queryInput = document.getElementById("query");
    if (queryInput) queryInput.value = text;
}

function addMessage(content, sender, imageUrl = null) {
    const messages = document.getElementById("messages");
    if (!messages) return;

    const msgDiv = document.createElement("div");
    msgDiv.className = sender === "user" ? "user-msg" : "bot-msg";
    msgDiv.innerHTML = content.replace(/\n/g, "<br>");

    if (imageUrl) {
        const img = document.createElement("img");
        img.src = imageUrl;
        img.className = "chat-thumb";
        msgDiv.appendChild(document.createElement("br"));
        msgDiv.appendChild(img);
    }

    messages.appendChild(msgDiv);
    messages.scrollTop = messages.scrollHeight;
}

function renderSources(sources) {
    const messages = document.getElementById("messages");
    if (!messages) return;

    const oldSources = document.getElementById("chatSourcesBlock");
    if (oldSources) oldSources.remove();

    if (!sources || sources.length === 0) return;

    const wrapper = document.createElement("div");
    wrapper.className = "bot-msg sources-chat-block";
    wrapper.id = "chatSourcesBlock";

    wrapper.innerHTML = `
        <div class="sources-heading">Sources</div>
        ${sources.map((item) => `
            <div class="source-item">
                <div><strong>Source:</strong> ${item.source || "N/A"}</div>
                ${item.filename ? `<div><strong>Filename:</strong> ${item.filename}</div>` : ""}
                ${item.section ? `<div><strong>Section:</strong> ${item.section}</div>` : ""}
                ${item.text ? `<div class="source-preview">${item.text}</div>` : ""}
            </div>
        `).join("")}
    `;

    messages.appendChild(wrapper);
    messages.scrollTop = messages.scrollHeight;
}

function saveHistoryItem(text) {
    if (!text) return;
    chatHistory.unshift(text);
    if (chatHistory.length > 8) chatHistory.pop();
    renderHistory();
}

function renderHistory() {
    const history = document.getElementById("history");
    if (!history) return;

    history.innerHTML = chatHistory.map(item => `
        <button type="button" onclick="reuseHistoryQuestion(${JSON.stringify(item)})">${item}</button>
    `).join("");
}

function reuseHistoryQuestion(text) {
    const queryInput = document.getElementById("query");
    if (queryInput) queryInput.value = text;
}

function newChat() {
    const messages = document.getElementById("messages");
    const query = document.getElementById("query");
    const symptoms = document.getElementById("symptoms");
    const preview = document.getElementById("preview");
    const fileName = document.getElementById("fileName");
    const imageInput = document.getElementById("imageInput");
    const oldSources = document.getElementById("chatSourcesBlock");
    if (oldSources) oldSources.remove();
    
    if (messages) messages.innerHTML = "";
    if (query) query.value = "";
    if (symptoms) symptoms.value = "";
    if (preview) {
        preview.src = "";
        preview.style.display = "none";
    }
    if (fileName) fileName.innerText = "";
    if (imageInput) imageInput.value = "";
    

    selectedImageFile = null;
}

function logout() {
    window.location.href = "/logout";
}

async function sendQuery() {
    const queryEl = document.getElementById("query");
    const symptomsEl = document.getElementById("symptoms");

    const query = queryEl ? queryEl.value.trim() : "";
    const symptoms = symptomsEl ? symptomsEl.value.trim() : "";

    if (!query) {
        alert("Please enter a question");
        return;
    }

    addMessage(`**You:** ${query}`, "user", selectedImageFile ? URL.createObjectURL(selectedImageFile) : null);

    try {
        let response, data;

        if (selectedImageFile) {
            const formData = new FormData();
            formData.append("image", selectedImageFile);
            formData.append("query", query);
            formData.append("symptoms", symptoms);

            response = await fetch("/upload_and_query", {
                method: "POST",
                body: formData
            });
        } else {
            const formData = new FormData();
            formData.append("query", query);

            response = await fetch("/ask_followup", {
                method: "POST",
                body: formData
            });
        }

        data = await response.json();

        if (!response.ok) {
            addMessage(data.detail || "Something went wrong", "bot");
            renderSources([]);
            return;
        }

        addMessage(data.response || "No response received.", "bot");
        renderSources(data.sources || []);
        saveHistoryItem(query);

        if (queryEl) queryEl.value = "";
        if (symptomsEl) symptomsEl.value = "";
        selectedImageFile = null;

        const preview = document.getElementById("preview");
        const fileName = document.getElementById("fileName");
        const imageInput = document.getElementById("imageInput");

        if (preview) {
            preview.src = "";
            preview.style.display = "none";
        }
        if (fileName) fileName.innerText = "";
        if (imageInput) imageInput.value = "";
    } catch (error) {
        console.error(error);
        addMessage("Something went wrong", "bot");
    }
}



async function loadMedicalProfile() {
    const form = document.getElementById("medicalProfileForm");
    if (!form) return;

    try {
        const res = await fetch("/medical_profile");
        if (!res.ok) return;

        const data = await res.json();
        form.age.value = data.age || "";
        form.gender.value = data.gender || "";
        form.blood_group.value = data.blood_group || "";
        form.allergies.value = data.allergies || "";
        form.diseases.value = data.diseases || "";
        form.medications.value = data.medications || "";
        form.emergency_contact.value = data.emergency_contact || "";
    } catch (err) {
        console.error("Failed to load profile:", err);
    }
}

document.addEventListener("DOMContentLoaded", function () {
    const medicalProfileForm = document.getElementById("medicalProfileForm");
    const profileMessage = document.getElementById("profileMessage");
    const loadKbBtn = document.getElementById("loadKbBtn");
    const kbMessage = document.getElementById("kbMessage");

    const userProfile = document.getElementById("userProfile");
    const userAvatar = document.getElementById("userAvatar");
    const userName = document.getElementById("userName");

    if (typeof currentUsername !== "undefined" && userProfile && userAvatar && userName) {
        userProfile.style.display = "flex";
        userName.innerText = currentUsername;
        userAvatar.innerText = currentUsername.charAt(0).toUpperCase();
    }

    renderHistory();
    loadMedicalProfile();

    if (medicalProfileForm) {
        medicalProfileForm.addEventListener("submit", async function (e) {
            e.preventDefault();
            if (profileMessage) profileMessage.innerText = "Saving...";

            try {
                const formData = new FormData(medicalProfileForm);

                const response = await fetch("/medical_profile", {
                    method: "POST",
                    body: formData
                });

                const data = await response.json();
                if (profileMessage) profileMessage.innerText = data.message || "Saved successfully";
            } catch (error) {
                if (profileMessage) profileMessage.innerText = "Failed to save profile";
                console.error(error);
            }
        });
    }

    if (loadKbBtn) {
        loadKbBtn.addEventListener("click", async function () {
            if (kbMessage) kbMessage.innerText = "Loading knowledge base...";

            try {
                const response = await fetch("/load_kb");
                const data = await response.json();

                if (data.status === "success") {
                    if (kbMessage) kbMessage.innerText = `Medical KB loaded. Chunks added: ${data.chunks_added}`;
                } else if (data.status === "already_loaded") {
                    if (kbMessage) kbMessage.innerText = "Medical KB already loaded.";
                } else {
                    if (kbMessage) kbMessage.innerText = data.message || "Failed to load KB";
                }
            } catch (error) {
                if (kbMessage) kbMessage.innerText = "Error loading KB";
                console.error(error);
            }
        });
    }
});

window.loginUser = loginUser;
window.signupUser = signupUser;
window.continueAsGuest = continueAsGuest;

window.login = login;
window.signup = signup;
window.guestLogin = guestLogin;

window.openFilePicker = openFilePicker;
window.previewImage = previewImage;
window.fillQuestion = fillQuestion;
window.newChat = newChat;
window.logout = logout;
window.sendQuery = sendQuery;
window.startVoiceInput = startVoiceInput;
window.reuseHistoryQuestion = reuseHistoryQuestion;