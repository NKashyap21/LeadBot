# PythonLeadAgent

A B2B lead generation agent that takes a natural language query, finds matching LinkedIn profiles via Google Search, enriches them with contact details, and writes everything to a Google Sheet automatically.

## How It Works

1. You provide a natural language query (e.g. *"supply chain and warehouse managers in Mumbai working at a 3PL company"*)
2. An LLM (Llama 3.3 70B via Groq) expands the query with relevant synonyms and keywords
3. SerpAPI searches Google for matching LinkedIn profiles
4. Hunter.io enriches each profile with email and phone number
5. SQLite deduplicates leads across runs so you never process the same person twice
6. All leads are written to a Google Sheet

---

## Project Structure

```
PythonLeadAgent/
├── app/                        # Core modules
├── main.py                     # Entry point
├── systemPrompt.txt            # LLM system prompt
├── leads.db                    # SQLite dedup cache (auto-created)
├── .env.example                # API keys 
├── pyproject.toml
└── uv.lock
```

---

## Setup

### 1. Clone and install dependencies

```bash
git clone https://github.com/NKashyap21/LeadBot.git
cd PythonLeadAgent
uv sync
```

---

## Obtaining API Keys

### Groq (LLM)

1. Go to [console.groq.com](https://console.groq.com)
2. Sign up for a free account
3. Navigate to **API Keys** → **Create API Key**
4. Copy the key — it starts with `gsk_...`

Free tier includes access to `llama-3.3-70b-versatile` with generous rate limits.

---

### SerpAPI (Google Search)

1. Go to [serpapi.com](https://serpapi.com)
2. Sign up — free tier gives you **100 searches/month**
3. Go to your **Dashboard** → copy your **API Key**

---

### Hunter.io (Email + Phone Enrichment)

1. Go to [hunter.io](https://hunter.io)
2. Sign up — free tier gives you **25 requests/month**
3. Go to **API** (in the top nav) → copy your **API Key**

---

## Google Sheets Setup

This project uses a **Google Service Account** to write to your sheet without any manual login.

### Step 1 — Create a Google Cloud Project

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Click **Select a project** → **New Project** → give it a name → **Create**

### Step 2 — Enable APIs

1. In the left sidebar go to **APIs & Services → Library**
2. Search for and enable **Google Sheets API**
3. Search for and enable **Google Drive API**

### Step 3 — Create a Service Account

1. Go to **IAM & Admin → Service Accounts**
2. Click **Create Service Account**
3. Give it a name (e.g. `leads-bot`) → click **Create and Continue** → **Done**
4. Click on the service account you just created
5. Go to the **Keys** tab → **Add Key** → **Create new key** → **JSON**
6. A `.json` file will download — rename it and place it in the project root 

### Step 4 — Share Your Google Sheet with the Service Account

1. Open the `.json` credentials file and copy the `client_email` field (looks like `leads-bot@your-project.iam.gserviceaccount.com`)
2. Open your Google Sheet
3. Click **Share** (top right)
4. Paste the service account email → set role to **Editor** → **Send**

> Without this step the bot will get a 403 permission error even with valid credentials.

### Step 5 — Add headers to your sheet manually

Add these headers in row 1 before running the bot:

| Name | Position | Company | Location | Email | Phone | LinkedIn URL |

---

## Environment Variables

Create a `.env` file in the project root:

```env
GROQ_API_KEY=gsk_...
SERP_API_KEY=...
HUNTER_API_KEY=...
GOOGLE_SHEET_NAME=Your Sheet Name Here
GOOGLE_CREDENTIALS_FILE=pythonleadsbot-xxxx.json
```

---

## Running the Agent

```bash
uv run main.py
```

You will be prompted to enter your query:

```
input: supply chain and warehouse managers in Mumbai working at a 3PL company
```

The agent will print progress as it runs and append all found leads to your Google Sheet.

---

## Notes

- The SQLite database (`leads.db`) is created automatically on first run and persists across runs for deduplication
- Hunter.io's free tier has a low request limit — upgrade if you need to process large volumes
- SerpAPI returns 10 results per search by default — this can be adjusted in the config
