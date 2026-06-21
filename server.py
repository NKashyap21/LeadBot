import os
import json
import sqlite3
import asyncio
from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import dotenv

# Load environment variables on startup
dotenv_path = dotenv.find_dotenv()
if not dotenv_path:
    # Create empty .env if not present
    with open(".env", "w", encoding="utf-8") as f:
        pass
    dotenv_path = ".env"
dotenv.load_dotenv(dotenv_path)

# Importing existing logic from app directory
from app.llm import EnrichQuery
from app.serp import SearchGoogle, parse_serp_results
from app.cache import is_duplicate, mark_seen
from langchain_groq import ChatGroq
import serpapi
import gspread

app = FastAPI(title="LeadBot API")

# Verification helper to secure the API endpoints
def verify_access(x_app_password: str = Header(None)):
    app_password = os.getenv("APP_PASSWORD")
    # If no APP_PASSWORD is configured, allow access (makes it easier to set up)
    if not app_password:
        return
    if x_app_password != app_password:
        raise HTTPException(status_code=401, detail="Unauthorized - Invalid Password")

# Mask keys for security when returning config to frontend
def mask_key(val: str) -> str:
    if not val:
        return ""
    if len(val) <= 8:
        return "********"
    return f"{val[:4]}...{val[-4:]}"

# Request and Response schemas
class PasswordVerifyRequest(BaseModel):
    password: str

class ConfigUpdateRequest(BaseModel):
    groq_api_key: str = None
    serp_api_key: str = None
    hunter_api_key: str = None
    google_sheet_name: str = None
    google_credentials_json: str = None  # Raw content of the JSON credentials file

class GenerateRequest(BaseModel):
    query: str

@app.get("/api/auth-status")
def get_auth_status():
    app_password = os.getenv("APP_PASSWORD")
    return {
        "auth_required": bool(app_password),
        "configured_status": {
            "groq": bool(os.getenv("GROQ_API_KEY")),
            "serp": bool(os.getenv("SERP_API_KEY")),
            "hunter": bool(os.getenv("HUNTER_API_KEY")),
            "sheets": bool(os.getenv("GOOGLE_SHEET_NAME")),
            "credentials": bool(os.getenv("GOOGLE_CREDENTIALS_FILE"))
        }
    }

@app.post("/api/verify-password")
def verify_password(req: PasswordVerifyRequest):
    app_password = os.getenv("APP_PASSWORD")
    if not app_password:
        return {"valid": True}
    return {"valid": req.password == app_password}

@app.get("/api/config", dependencies=[Depends(verify_access)])
def get_config():
    # Return current keys in masked format
    credentials_file = os.getenv("GOOGLE_CREDENTIALS_FILE", "")
    has_credentials = False
    if credentials_file and os.path.exists(credentials_file):
        has_credentials = True

    return {
        "groq_api_key": mask_key(os.getenv("GROQ_API_KEY")),
        "serp_api_key": mask_key(os.getenv("SERP_API_KEY")),
        "hunter_api_key": mask_key(os.getenv("HUNTER_API_KEY")),
        "google_sheet_name": os.getenv("GOOGLE_SHEET_NAME", ""),
        "has_google_credentials": has_credentials
    }

@app.post("/api/config", dependencies=[Depends(verify_access)])
def update_config(req: ConfigUpdateRequest):
    global dotenv_path
    
    # 1. Update API Keys in .env
    if req.groq_api_key and not req.groq_api_key.startswith("gsk_..."): # Skip updating if masked placeholder sent
        dotenv.set_key(dotenv_path, "GROQ_API_KEY", req.groq_api_key)
        os.environ["GROQ_API_KEY"] = req.groq_api_key
        
    if req.serp_api_key and not req.serp_api_key.startswith("****"):
        dotenv.set_key(dotenv_path, "SERP_API_KEY", req.serp_api_key)
        os.environ["SERP_API_KEY"] = req.serp_api_key
        
    if req.hunter_api_key and not req.hunter_api_key.startswith("****"):
        dotenv.set_key(dotenv_path, "HUNTER_API_KEY", req.hunter_api_key)
        os.environ["HUNTER_API_KEY"] = req.hunter_api_key
        
    if req.google_sheet_name is not None:
        dotenv.set_key(dotenv_path, "GOOGLE_SHEET_NAME", req.google_sheet_name)
        os.environ["GOOGLE_SHEET_NAME"] = req.google_sheet_name

    # 2. Write Google Credentials if provided
    if req.google_credentials_json:
        try:
            # Validate JSON content
            creds_data = json.loads(req.google_credentials_json)
            creds_filename = "google-credentials.json"
            
            with open(creds_filename, "w", encoding="utf-8") as f:
                json.dump(creds_data, f, indent=4)
                
            dotenv.set_key(dotenv_path, "GOOGLE_CREDENTIALS_FILE", creds_filename)
            os.environ["GOOGLE_CREDENTIALS_FILE"] = creds_filename
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid Google credentials JSON format: {str(e)}")

    # Force reload of dotenv in case process values got stale
    dotenv.load_dotenv(dotenv_path)
    return {"status": "success", "message": "Configuration saved successfully."}

@app.post("/api/generate", dependencies=[Depends(verify_access)])
def generate_leads(req: GenerateRequest):
    
    async def sse_event_generator():
        try:
            # Load fresh values from env
            groq_key = os.getenv("GROQ_API_KEY")
            serp_key = os.getenv("SERP_API_KEY")
            hunter_key = os.getenv("HUNTER_API_KEY")
            sheet_name = os.getenv("GOOGLE_SHEET_NAME")
            credentials_file = os.getenv("GOOGLE_CREDENTIALS_FILE")

            if not groq_key or not serp_key or not hunter_key or not sheet_name or not credentials_file:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Missing configuration! Please fill in all API Keys and Google Sheet details in Settings.'})}\n\n"
                return

            yield f"data: {json.dumps({'type': 'status', 'message': 'Connecting to Groq, SerpAPI, and Google Sheets...'})}\n\n"
            await asyncio.sleep(0.1) # Yield to event loop

            try:
                model = ChatGroq(model="llama-3.3-70b-versatile", api_key=groq_key)
                client = serpapi.Client(api_key=serp_key)
                gc = gspread.service_account(filename=credentials_file)
                sheet = gc.open(sheet_name).sheet1
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': f'Client initialization error: {str(e)}'})}\n\n"
                return

            # Refinement via LLM
            yield f"data: {json.dumps({'type': 'status', 'message': 'Refining natural language query using ChatGroq...'})}\n\n"
            await asyncio.sleep(0.1)
            
            resp, err = EnrichQuery(model, req.query)
            if err:
                yield f"data: {json.dumps({'type': 'error', 'message': f'Groq LLM Enrichment failed: {err}'})}\n\n"
                return

            yield f"data: {json.dumps({'type': 'status', 'message': f'Query refined to SerpAPI params: {json.dumps(resp)}'})}\n\n"
            await asyncio.sleep(0.1)

            # Search Google via SerpAPI
            yield f"data: {json.dumps({'type': 'status', 'message': 'Searching Google for LinkedIn profiles via SerpAPI...'})}\n\n"
            await asyncio.sleep(0.1)
            
            results, err = SearchGoogle(client, resp)
            if err:
                yield f"data: {json.dumps({'type': 'error', 'message': f'SerpAPI Google Search failed: {err}'})}\n\n"
                return

            final_result = parse_serp_results(results)
            yield f"data: {json.dumps({'type': 'status', 'message': f'SerpAPI returned {len(final_result)} LinkedIn profiles.'})}\n\n"
            await asyncio.sleep(0.1)

            if not final_result:
                yield f"data: {json.dumps({'type': 'done', 'message': 'No leads found. Process finished.'})}\n\n"
                return

            # Cache & Deduplicate via SQLite
            yield f"data: {json.dumps({'type': 'status', 'message': 'Filtering duplicate leads using SQLite cache...'})}\n\n"
            await asyncio.sleep(0.1)
            
            new_leads = []
            with sqlite3.connect("leads.db") as connection:
                cursor = connection.cursor()
                cursor.execute("CREATE TABLE IF NOT EXISTS leads_seen(linkedin_url TEXT PRIMARY KEY)")
                
                for lead in final_result:
                    linkedin_url = lead.get("linkedin_url")
                    name = lead.get("name")
                    if not is_duplicate(connection, linkedin_url):
                        new_leads.append(lead)
                        yield f"data: {json.dumps({'type': 'lead_found', 'lead': lead})}\n\n"
                    else:
                        yield f"data: {json.dumps({'type': 'lead_skipped', 'name': name})}\n\n"
                    await asyncio.sleep(0.05)

            if not new_leads:
                yield f"data: {json.dumps({'type': 'status', 'message': 'All leads returned are duplicates already processed in previous runs.'})}\n\n"
                yield f"data: {json.dumps({'type': 'done', 'message': 'Process completed. 0 new leads found.'})}\n\n"
                return

            # Email Finder via Hunter.io (stream one-by-one)
            yield f"data: {json.dumps({'type': 'status', 'message': f'Enriching contact emails for {len(new_leads)} new leads via Hunter.io...'})}\n\n"
            await asyncio.sleep(0.1)

            import requests
            enriched_leads = []
            for lead in new_leads:
                lead["email"] = None
                lead["phone_number"] = None
                linkedin_url = lead.get("linkedin_url")

                if linkedin_url:
                    try:
                        # Extract handle or use full profile URL as Hunter.io supports LinkedIn handles
                        response = requests.get(
                            "https://api.hunter.io/v2/email-finder",
                            params={"linkedin_handle": linkedin_url, "api_key": hunter_key},
                            timeout=15
                        )
                        if response.status_code == 200:
                            res_data = response.json()
                            if not res_data.get("errors"):
                                data = res_data.get("data", {})
                                lead["email"] = data.get("email")
                                lead["phone_number"] = data.get("phone_number")
                    except Exception as e:
                        # Yield warning but continue for other leads
                        warning_msg = f"Warning: Hunter.io lookup error for {lead.get('name')}: {str(e)}"
                        yield f"data: {json.dumps({'type': 'status', 'message': warning_msg})}\n\n"

                enriched_leads.append(lead)
                yield f"data: {json.dumps({'type': 'lead_enriched', 'lead': lead})}\n\n"
                await asyncio.sleep(0.1)

            # Append to Google Sheets and commit database
            yield f"data: {json.dumps({'type': 'status', 'message': f'Writing enriched leads to Google Sheet: \"{sheet_name}\"...'})}\n\n"
            await asyncio.sleep(0.1)

            with sqlite3.connect("leads.db") as connection:
                for lead in enriched_leads:
                    name = lead.get("name")
                    email = lead.get("email")
                    phoneNum = lead.get("phone_number")
                    company = lead.get("company")
                    position = lead.get("position")
                    linkedin_url = lead.get("linkedin_url")
                    location = lead.get("location")

                    try:
                        sheet.append_row([name, email, phoneNum, company, position, linkedin_url, location])
                        mark_seen(connection, linkedin_url)
                        yield f"data: {json.dumps({'type': 'lead_saved', 'name': name})}\n\n"
                    except Exception as sheet_err:
                        err_msg = f"Failed to write lead \"{name}\" to sheet: {str(sheet_err)}"
                        yield f"data: {json.dumps({'type': 'error', 'message': err_msg})}\n\n"
                        return
                    await asyncio.sleep(0.1)

            yield f"data: {json.dumps({'type': 'done', 'message': f'Successfully parsed and added {len(enriched_leads)} leads to Google Sheets!'})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': f'Server stream failure: {str(e)}'})}\n\n"

    return StreamingResponse(sse_event_generator(), media_type="text/event-stream")

# Serve UI static files
# Place static folder and files
@app.get("/")
def get_index():
    if os.path.exists("static/index.html"):
        return FileResponse("static/index.html")
    return {"error": "UI static files not compiled yet."}

# Mount static directory for JS and CSS files
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")
