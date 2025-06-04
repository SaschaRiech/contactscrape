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
    emails = re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", text, re.I)
    return list(set(emails))

def extract_uk_mobile_numbers(text):
    pattern = re.compile(
        r"(?:(?:\+44\s?7\d{3})|(?:07\d{3}))[ \-]?\d{3}[ \-]?\d{3,4}",
        re.VERBOSE
    )
    matches = pattern.findall(text)
    normalized = set()
    for match in matches:
        phone = re.sub(r"[^\d]", "", match)
        if phone.startswith("07"):
            phone = "+44" + phone[1:]
        elif phone.startswith("44"):
            phone = "+" + phone
        normalized.add(phone)
    return list(normalized)

def fetch_page_text(url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0"
        }
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        return soup.get_text(separator=" ", strip=True)
    except Exception as e:
        st.write(f"Error fetching {url}: {e}")
        return ""

def main():
    st.title("UK Contact Finder (Prototype)")

    name = st.text_input("Full Name (e.g., John Doe)", "")
    company = st.text_input("Company (optional)", "")

    if st.button("Search"):
        if not name.strip():
            st.warning("Please enter a full name.")
            return

        query = f'"{name.strip()}"'
        if company:
            query += f' "{company.strip()}"'
        query += ' email OR phone OR contact site:linkedin.com OR site:company.co.uk'

        st.info(f"Searching for: `{query}`")
        results = serpapi_search(query, num_results=10)

        if not results:
            st.error("No results found.")
            return

        found_emails = set()
        found_phones = set()

        visited_urls = set()

        for result in results:
            url = result.get("link")
            if not url or url in visited_urls:
                continue
            visited_urls.add(url)

            st.markdown(f"#### Scanning: [{result.get('title')}]({url})")

            page_text = fetch_page_text(url)
            if not page_text:
                st.write("No content found.")
                continue

            emails = extract_emails(page_text)
            phones = extract_uk_mobile_numbers(page_text)

            if emails:
                found_emails.update(emails)
                st.write("Emails:", ", ".join(emails))
            else:
                st.write("No emails found.")

            if phones:
                found_phones.update(phones)
                st.write("Mobile Numbers:", ", ".join(phones))
            else:
                st.write("No phone numbers found.")

        st.markdown("---")
        st.subheader("Final Extracted Contacts")

        if found_emails:
            st.write("📧 Emails:")
            for e in sorted(found_emails):
                st.write(f"- {e}")
        else:
            st.write("No emails found.")

        if found_phones:
            st.write("📱 Mobile Numbers:")
            for p in sorted(found_phones):
                st.write(f"- {p}")
        else:
            st.write("No UK mobile numbers found.")

if __name__ == "__main__":
    main()

