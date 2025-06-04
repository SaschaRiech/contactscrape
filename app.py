import streamlit as st
import requests
import re

SERPAPI_API_KEY = st.secrets["SERPAPI_API_KEY"]

def serpapi_search(query):
    params = {
        "engine": "google",
        "q": query,
        "api_key": SERPAPI_API_KEY,
        "num": 5
    }
    response = requests.get("https://serpapi.com/search", params=params)
    st.write(f"SerpAPI response status: {response.status_code}")
    st.write(f"SerpAPI response text: {response.text[:500]}")  # Debug output

    if response.status_code != 200:
        st.error(f"SerpAPI error: {response.status_code} - {response.text}")
        return []

    data = response.json()
    results = []
    for result in data.get("organic_results", []):
        results.append({"title": result.get("title"), "link": result.get("link"), "snippet": result.get("snippet")})
    return results

def extract_emails(text):
    emails = re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", text)
    return list(set(emails))  # Remove duplicates

def extract_phones(text):
    # UK mobile number patterns:
    # Format examples: 07123 456789, +44 7123 456789, 07123456789, +447123456789
    pattern = re.compile(
        r'(?:\+44\s?7\d{3}|\b07\d{3})\s?\d{3}\s?\d{3}\b'
    )
    phones = pattern.findall(text)
    # Normalize phones: remove spaces and format uniformly (optional)
    normalized = set()
    for phone in phones:
        # Remove spaces, keep +44 or 0 prefix
        p = phone.replace(" ", "")
        if p.startswith("07"):
            p = "+44" + p[1:]  # Convert 07... to +447...
        normalized.add(p)
    return list(normalized)

def get_page_text(url):
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            return resp.text
    except:
        return ""
    return ""

def main():
    st.title("Contact Finder Prototype with SerpAPI")
    name = st.text_input("Full Name", "")
    company = st.text_input("Company (optional)", "")
    
    if st.button("Search"):
        if not name:
            st.warning("Please enter a name.")
            return
        
        query = f'"{name}"'
        if company:
            query += f' "{company}"'
        query += " contact OR email OR phone"

        st.info("Searching Google via SerpAPI...")
        results = serpapi_search(query)
        
        if not results:
            st.write("No search results found.")
            return
        
        contacts_found = []
        for res in results:
            page_text = get_page_text(res["link"])
            emails = extract_emails(page_text)
            phones = extract_phones(page_text)
            if emails or phones:
                contacts_found.append({"url": res["link"], "emails": emails, "phones": phones})

        if not contacts_found:
            st.write("No contacts found in the search results.")
        else:
            for contact in contacts_found:
                st.markdown(f"### URL: [{contact['url']}]({contact['url']})")
                if contact['emails']:
                    st.write("Emails:", ", ".join(contact['emails']))
                if contact['phones']:
                    st.write("Mobile Phones:", ", ".join(contact['phones']))

if __name__ == "__main__":
    main()

