import requests

def GetEmail(leads: list[dict], apiKey: str) -> list[dict]:
    api_end_point = "https://api.hunter.io/v2/email-finder"

    for lead in leads:
        # Default values
        lead["email"] = None
        lead["phone_number"] = None

        linkedin_profile = lead.get("linkedin_url")

        if not linkedin_profile:
            continue

        params = {
            "linkedin_handle": linkedin_profile,
            "api_key": apiKey
        }

        try:
            response = requests.get(
                api_end_point,
                params=params
            ).json()

            if response.get("errors"):
                continue

            data = response.get("data", {})

            lead["email"] = data.get("email")
            lead["phone_number"] = data.get("phone_number")

        except Exception as e:
            print(f"Error processing {lead.get('name')}: {e}")

    return leads
