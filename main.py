from app.llm import EnrichQuery
from app.serp import SearchGoogle,parse_serp_results
from app.hunter import GetEmail
from app.cache import is_duplicate,mark_seen

from langchain_groq import ChatGroq
import sqlite3
import serpapi
import gspread
from dotenv import load_dotenv
import os

load_dotenv()

##Initializing all the clients
model = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=os.getenv("GROQ_API_KEY")
)
client = serpapi.Client(api_key=os.getenv("SERP_API_KEY"))
gc = gspread.service_account(filename=os.getenv("GOOGLE_CREDENTIALS_FILE"))
sheet = gc.open(os.getenv("GOOGLE_SHEET_NAME")).sheet1

with sqlite3.connect("leads.db") as connection:
    cursor = connection.cursor()

    #Create the Leads Table
    cursor.execute("CREATE TABLE IF NOT EXISTS leads_seen(linkedin_url TEXT PRIMARY KEY)")

    query = input("Input: ")

    #Send to LLM to refine 
    print(f"{"\033[92m"}Sending to LLM from enrichment...{"\033[0m"}")
    resp,err = EnrichQuery(model,query)
    if err != "":
        print(f"{"\033[91m"}{err}{"\033[0m"}")
        

    #Send to Serp Api (And get links)
    print(f"{"\033[92m"}Connecting to SerpApi...{"\033[0m"}")
    results,err = SearchGoogle(client,resp)
    if err != "":
        print(f"{"\033[91m"}{err}{"\033[0m"}")
        
    final_result = parse_serp_results(results)

    #Use Sqlite to store leads.
    print(f"{"\033[92m"}Checking sqlite...{"\033[0m"}")
    final_leads = [] 
    for lead in final_result:
        if not is_duplicate(connection,lead["linkedin_url"]):
            final_leads.append(lead)
        else:
            print(f"Skipping lead: {lead["name"]}")
            continue 
    #Use Hunter Api to get Email, 
    print(f"{"\033[92m"}Connecting to HunterApi...{"\033[0m"}")
    final_result = GetEmail(final_leads,os.getenv("HUNTER_API_KEY"))

    #Store Name,Email,Phone,Company Name, Position, LinkedIn Profile into google sheets
    print(f"{"\033[92m"}Sending data to google sheets...{"\033[0m"}")
    for lead in final_result:
        name = lead.get("name")
        email = lead.get("email")
        phoneNum = lead.get("phone_number")
        comapny = lead.get("company")
        position = lead.get("position")
        linkedIn_profile = lead.get("linkedin_url")
        location = lead.get("location")

        sheet.append_row([name,email,phoneNum,comapny,position,linkedIn_profile,location])
        mark_seen(connection,linkedIn_profile)

