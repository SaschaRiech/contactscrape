import streamlit as st
import requests
import re
from bs4 import BeautifulSoup

SERPAPI_API_KEY = st.secrets["SERPAPI_API_KEY"]

def serpapi_search(query, num_results=10):
    params = {
        "engine": "google",
        "q": query,
        "api_key": SERPAPI_API_KEY,
        "num": num_results
    }
    try:
        response = requests.get("https://serpapi.com/search", params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        return data.get("organic_results", [])
    except requests.RequestException as e:
        st.error(f"Error fetching search results: {e}")
        return []

def extract_emails(text):
    # Common email regex, case insensitive
    emails = re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", text, re.I)
    return list(set(emails))

def extract_uk_mobile_numbers(text):
    # Match UK mobile numbers in various common formats
    pattern = re.compile(
        r"(?:\+44\s?7\d{3}|\(?07\d{3}\)?)\s?\d{3}\s?\d{3,4}", re.I
    )
    matches = pattern.findall(text)
    normalized = set()
    for match in matches:
        # Normalize phone: remove spaces, brackets; convert leading 07 to +447
        phone = match.replace(" ", "").replace("(", "").replace(")", "")
        if phone.startswith("07"):
            phone = "+44" + phone[1:]
        normalized.add(phone)
    return list(normalized)

def fetch_page_text(url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; ContactFinder/1.0; +https://example.com/bot)"
        }
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        # Use BeautifulSoup to extract visible text (better than raw HTML)
        soup = BeautifulSoup(resp.text, "html.parser")
        # Remove script and style tags
        for script_or_style in soup(["script", "style", "noscript"]):
            script_or_style.decompose()
        text = soup.get_text(separator=" ", strip=True)
        return text
    except requests.RequestException:
        return ""

def main():
    st.title("Free UK Contact Finder Prototype")

    name = st.text_input("Full Name (required)", "")
    company = st.text_input("Company (optional)", "")
    if st.button("Find Contacts"):
        if not name.strip():
            st.warning("Please enter a full name.")
            return
        
        query = f'"{name.strip()}"'
        if company.strip():
            query += f' "{company.strip()}"'
        query += " contact OR email OR phone"

        st.info("Searching Google via SerpAPI...")
        results = serpapi_search(query, num_results=10)

        if not results:
            st.write("No results found for your query.")
            return
        
        all_emails = set()
        all_phones = set()
        st.write(f"Found {len(results)} search results. Extracting contacts...")

        for result in results:
            url = result.get("link")
            st.markdown(f"### [{result.get('title')}]({url})")
            page_text = fetch_page_text(url)
            if not page_text:
                st.write("_Failed to fetch or parse page text._")
                continue

            emails = extract_emails(page_text)
            phones = extract_uk_mobile_numbers(page_text)

            if emails:
                all_emails.update(emails)
                st.write("Emails:", ", ".join(emails))
            else:
                st.write("Emails: None found")

            if phones:
                all_phones.update(phones)
                st.write("Mobile Phones:", ", ".join(phones))
            else:
                st.write("Mobile Phones: None found")

        if not all_emails and not all_phones:
            st.warning("No emails or UK mobile numbers found in the search results.")

        else:
            st.success("Summary of unique contacts found:")
            if all_emails:
                st.write("**Emails:**", ", ".join(sorted(all_emails)))
            if all_phones:
                st.write("**Mobile Phones:**", ", ".join(sorted(all_phones)))

if __name__ == "__main__":
    main()


