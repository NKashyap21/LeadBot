import serpapi

def SearchGoogle(client:serpapi.Client,params:dict) -> (dict,str):
    try:
        results = client.search(params)
        return results,""
    except Exception as e:
        return {},str(e)


def parse_serp_results(response: dict) -> list[dict]:
    leads = []
    
    for result in response.get("organic_results", []):
        title = result.get("title", "")
        name = title.split(" - ")[0].strip()
        
        linkedin_url = result.get("link", "")
        
        # extensions = [location, position, company]
        extensions = result.get("rich_snippet", {}).get("top", {}).get("extensions", [])
        location = extensions[0] if len(extensions) > 0 else ""
        position = extensions[1] if len(extensions) > 1 else ""
        company  = extensions[2] if len(extensions) > 2 else ""
        
        leads.append({
            "name":         name,
            "linkedin_url": linkedin_url,
            "location":     location,
            "position":     position,
            "company":      company,
        })
    
    return leads