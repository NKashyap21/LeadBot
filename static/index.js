// UI State and Selectors
const loginScreen = document.getElementById('login-screen');
const dashboard = document.getElementById('dashboard');
const loginForm = document.getElementById('login-form');
const loginError = document.getElementById('login-error');
const passwordInput = document.getElementById('password');

const btnSettings = document.getElementById('btn-settings');
const btnCloseSettings = document.getElementById('btn-close-settings');
const btnLogout = document.getElementById('btn-logout');
const searchCard = document.getElementById('search-card');
const settingsCard = document.getElementById('settings-card');
const warningNoAuth = document.getElementById('warning-no-auth');

const searchForm = document.getElementById('search-form');
const queryInput = document.getElementById('query-input');
const btnRun = document.getElementById('btn-run');
const statusBadge = document.getElementById('status-badge');
const stepperSpinner = document.getElementById('stepper-spinner');

const logConsole = document.getElementById('log-console');
const leadsCount = document.getElementById('leads-count');
const leadsBody = document.getElementById('leads-body');

const settingsForm = document.getElementById('settings-form');
const groqKeyInput = document.getElementById('groq-key');
const serpKeyInput = document.getElementById('serp-key');
const hunterKeyInput = document.getElementById('hunter-key');
const sheetNameInput = document.getElementById('sheet-name');
const credentialsJsonInput = document.getElementById('credentials-json');
const settingsMsg = document.getElementById('settings-msg');
const settingsError = document.getElementById('settings-error');

// Stepper Step Elements
const steps = {
    llm: document.getElementById('step-llm'),
    serp: document.getElementById('step-serp'),
    dedup: document.getElementById('step-dedup'),
    hunter: document.getElementById('step-hunter'),
    sheets: document.getElementById('step-sheets')
};

// State Variables
let currentLeads = []; // Track leads in the active run session
let authRequired = false;

// 1. Password/Authentication Helpers
function getPassword() {
    return localStorage.getItem('leadbot_password') || '';
}

function setPassword(pass) {
    localStorage.setItem('leadbot_password', pass);
}

function clearPassword() {
    localStorage.removeItem('leadbot_password');
}

// Check initial authentication status
async function initAuth() {
    try {
        const res = await fetch('/api/auth-status');
        const data = await res.json();
        authRequired = data.auth_required;
        
        if (authRequired) {
            const currentPass = getPassword();
            if (currentPass) {
                // Verify saved password
                const valid = await verifyPasswordOnServer(currentPass);
                if (valid) {
                    showDashboard();
                } else {
                    clearPassword();
                    showLogin();
                }
            } else {
                showLogin();
            }
        } else {
            showDashboard();
            warningNoAuth.classList.remove('hidden');
        }
    } catch (err) {
        console.error("Auth initialization failed: ", err);
        showLogin();
    }
}

async function verifyPasswordOnServer(pass) {
    try {
        const res = await fetch('/api/verify-password', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ password: pass })
        });
        const data = await res.json();
        return data.valid;
    } catch (err) {
        return false;
    }
}

function showLogin() {
    loginScreen.classList.remove('hidden');
    dashboard.classList.add('hidden');
    passwordInput.focus();
}

function showDashboard() {
    loginScreen.classList.add('hidden');
    dashboard.classList.remove('hidden');
    loadConfig();
}

// Login form submit handler
loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    loginError.classList.add('hidden');
    const pass = passwordInput.value.trim();
    
    const valid = await verifyPasswordOnServer(pass);
    if (valid) {
        setPassword(pass);
        passwordInput.value = '';
        showDashboard();
    } else {
        loginError.classList.remove('hidden');
    }
});

// Logout handler
btnLogout.addEventListener('click', () => {
    clearPassword();
    window.location.reload();
});

// 2. Settings Management
btnSettings.addEventListener('click', () => {
    searchCard.classList.add('hidden');
    settingsCard.classList.remove('hidden');
});

btnCloseSettings.addEventListener('click', () => {
    settingsCard.classList.add('hidden');
    searchCard.classList.remove('hidden');
});

async function loadConfig() {
    try {
        const res = await fetch('/api/config', {
            headers: { 'X-App-Password': getPassword() }
        });
        if (res.status === 401) {
            clearPassword();
            showLogin();
            return;
        }
        
        const data = await res.json();
        
        // Pre-fill inputs with masked placeholders
        groqKeyInput.value = data.groq_api_key ? "gsk_..." : "";
        serpKeyInput.value = data.serp_api_key ? "****" : "";
        hunterKeyInput.value = data.hunter_api_key ? "****" : "";
        sheetNameInput.value = data.google_sheet_name || "";
        
        if (data.has_google_credentials) {
            credentialsJsonInput.placeholder = "Google sheets credentials are configured. Paste a new JSON to update them.";
        } else {
            credentialsJsonInput.placeholder = 'Paste your complete download credentials.json here...';
        }
        credentialsJsonInput.value = '';
    } catch (err) {
        console.error("Failed to load configuration keys:", err);
    }
}

settingsForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    settingsMsg.classList.add('hidden');
    settingsError.classList.add('hidden');
    
    const body = {
        groq_api_key: groqKeyInput.value,
        serp_api_key: serpKeyInput.value,
        hunter_api_key: hunterKeyInput.value,
        google_sheet_name: sheetNameInput.value,
        google_credentials_json: credentialsJsonInput.value.trim() || null
    };

    try {
        const res = await fetch('/api/config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-App-Password': getPassword()
            },
            body: JSON.stringify(body)
        });
        
        if (res.ok) {
            settingsMsg.classList.remove('hidden');
            loadConfig();
            setTimeout(() => {
                settingsMsg.classList.add('hidden');
            }, 3000);
        } else {
            const data = await res.json();
            settingsError.textContent = data.detail || "Failed to save configuration.";
            settingsError.classList.remove('hidden');
        }
    } catch (err) {
        settingsError.textContent = "Network error. Failed to save configuration.";
        settingsError.classList.remove('hidden');
    }
});

// 3. Lead Generation Execution (SSE Stream)
searchForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const query = queryInput.value.trim();
    if (!query) return;
    
    // UI Reset
    resetTimeline();
    logConsole.innerHTML = '';
    addConsoleLog("Starting lead generation job...", "info");
    
    statusBadge.textContent = "Running";
    statusBadge.className = "badge running";
    stepperSpinner.classList.remove('hidden');
    btnRun.disabled = true;
    btnRun.querySelector('span').textContent = "Processing Leads...";
    
    currentLeads = [];
    updateLeadsTable();
    
    try {
        const response = await fetch('/api/generate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-App-Password': getPassword()
            },
            body: JSON.stringify({ query: query })
        });
        
        if (response.status === 401) {
            addConsoleLog("Authentication expired. Please log in again.", "error");
            clearPassword();
            showLogin();
            resetControls();
            return;
        }

        if (!response.ok) {
            const errData = await response.json();
            addConsoleLog(`HTTP Error: ${errData.detail || response.statusText}`, "error");
            resetControls();
            return;
        }

        // Connect reader to stream
        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let buffer = '';

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop(); // Keep the last incomplete block in buffer

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const jsonStr = line.substring(6).trim();
                    if (jsonStr) {
                        try {
                            const event = JSON.parse(jsonStr);
                            handleStreamEvent(event);
                        } catch (parseErr) {
                            console.error("Failed to parse SSE payload:", jsonStr, parseErr);
                        }
                    }
                }
            }
        }
    } catch (netErr) {
        addConsoleLog(`Connection terminated: ${netErr.message}`, "error");
    } finally {
        resetControls();
    }
});

function handleStreamEvent(event) {
    switch (event.type) {
        case 'status':
            addConsoleLog(event.message, "info");
            updateTimelineStatus(event.message);
            break;
            
        case 'lead_found':
            addConsoleLog(`Found LinkedIn Profile: ${event.lead.name} (${event.lead.company || 'Unknown Company'})`, "info");
            // Add lead with status Found
            event.lead.status = "Found";
            currentLeads.push(event.lead);
            updateLeadsTable();
            break;
            
        case 'lead_skipped':
            addConsoleLog(`Skipping lead: ${event.name} (Already in SQLite cache)`, "warning");
            // Add lead with status Skipped
            currentLeads.push({
                name: event.name,
                linkedin_url: "#",
                location: "",
                position: "",
                company: "",
                email: null,
                phone_number: null,
                status: "Skipped"
            });
            updateLeadsTable();
            break;
            
        case 'lead_enriched':
            const foundIdx = currentLeads.findIndex(l => l.linkedin_url === event.lead.linkedin_url);
            if (foundIdx !== -1) {
                currentLeads[foundIdx] = {
                    ...currentLeads[foundIdx],
                    email: event.lead.email,
                    phone_number: event.lead.phone_number,
                    status: "Enriched"
                };
                addConsoleLog(`Enriched details for ${event.lead.name}: Email found: ${event.lead.email || 'None'}`, "success");
                updateLeadsTable();
            }
            break;
            
        case 'lead_saved':
            const savedIdx = currentLeads.findIndex(l => l.name === event.name);
            if (savedIdx !== -1) {
                currentLeads[savedIdx].status = "Saved";
                updateLeadsTable();
            }
            addConsoleLog(`Saved lead "${event.name}" to Google Sheet.`, "success");
            break;
            
        case 'error':
            addConsoleLog(`Error: ${event.message}`, "error");
            statusBadge.textContent = "Failed";
            statusBadge.className = "badge";
            statusBadge.style.color = "var(--error)";
            statusBadge.style.background = "rgba(239, 68, 68, 0.15)";
            statusBadge.style.borderColor = "rgba(239, 68, 68, 0.3)";
            break;
            
        case 'done':
            addConsoleLog(event.message, "success");
            statusBadge.textContent = "Done";
            statusBadge.className = "badge done";
            
            // Mark all stepper elements complete
            Object.values(steps).forEach(step => {
                step.classList.remove('active');
                step.classList.add('complete');
            });
            break;
    }
}

// Helper to log message in monospaced console log
function addConsoleLog(message, type = "info") {
    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    
    // Add timestamp
    const now = new Date();
    const timeStr = now.toTimeString().split(' ')[0];
    entry.textContent = `[${timeStr}] ${message}`;
    
    logConsole.appendChild(entry);
    logConsole.scrollTop = logConsole.scrollHeight;
}

// Update stepper states based on diagnostic strings
function updateTimelineStatus(message) {
    if (message.includes("Groq")) {
        setActiveStep('llm');
    } else if (message.includes("SerpAPI")) {
        setCompleteStep('llm');
        setActiveStep('serp');
    } else if (message.includes("SQLite")) {
        setCompleteStep('serp');
        setActiveStep('dedup');
    } else if (message.includes("Hunter.io")) {
        setCompleteStep('dedup');
        setActiveStep('hunter');
    } else if (message.includes("Writing enriched leads") || message.includes("Appending leads")) {
        setCompleteStep('hunter');
        setActiveStep('sheets');
    }
}

function setActiveStep(key) {
    Object.keys(steps).forEach(k => {
        if (k === key) {
            steps[k].classList.add('active');
            steps[k].classList.remove('complete');
        }
    });
}

function setCompleteStep(key) {
    if (steps[key]) {
        steps[key].classList.remove('active');
        steps[key].classList.add('complete');
    }
}

function resetTimeline() {
    Object.values(steps).forEach(step => {
        step.classList.remove('active', 'complete');
    });
}

function resetControls() {
    stepperSpinner.classList.add('hidden');
    btnRun.disabled = false;
    btnRun.querySelector('span').textContent = "Find & Enrich Leads";
    if (statusBadge.textContent === "Running") {
        statusBadge.textContent = "Ready";
        statusBadge.className = "badge";
    }
}

// Render dynamic results list
function updateLeadsTable() {
    leadsBody.innerHTML = '';
    
    // Update total badge count
    const filteredLeads = currentLeads.filter(l => l.status !== "Skipped");
    leadsCount.textContent = `${filteredLeads.length} Leads`;
    
    if (currentLeads.length === 0) {
        leadsBody.innerHTML = `
            <tr id="empty-table-row">
                <td colspan="8" class="text-center">No leads processed yet in this session.</td>
            </tr>
        `;
        return;
    }
    
    currentLeads.forEach(lead => {
        const tr = document.createElement('tr');
        
        let statusBadge = '';
        if (lead.status === 'Found') {
            statusBadge = `<span class="status-indicator found">Found</span>`;
        } else if (lead.status === 'Enriched') {
            statusBadge = `<span class="status-indicator enriched">Enriched</span>`;
        } else if (lead.status === 'Saved') {
            statusBadge = `<span class="status-indicator saved">Saved to Sheet</span>`;
        } else if (lead.status === 'Skipped') {
            statusBadge = `<span class="status-indicator skipped">Skipped (Duplicate)</span>`;
        }
        
        const emailContent = lead.email ? `<span class="email-badge">${lead.email}</span>` : `<span class="text-muted">—</span>`;
        const phoneContent = lead.phone_number ? `<span>${lead.phone_number}</span>` : `<span class="text-muted">—</span>`;
        const linkedinLink = lead.linkedin_url && lead.linkedin_url !== "#" 
            ? `<a href="${lead.linkedin_url}" target="_blank" class="link-btn">
                View Profile
               </a>` 
            : `<span class="text-muted">—</span>`;
            
        tr.innerHTML = `
            <td><strong>${lead.name}</strong></td>
            <td>${lead.position || '<span class="text-muted">—</span>'}</td>
            <td>${lead.company || '<span class="text-muted">—</span>'}</td>
            <td>${lead.location || '<span class="text-muted">—</span>'}</td>
            <td>${emailContent}</td>
            <td>${phoneContent}</td>
            <td>${linkedinLink}</td>
            <td>${statusBadge}</td>
        `;
        leadsBody.appendChild(tr);
    });
}

// 4. Initial Trigger
initAuth();
