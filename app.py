import streamlit as st
import re
import requests
from bs4 import BeautifulSoup
import logging
import pandas as pd
from typing import List, Set
import time

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants
SERPAPI_API_KEY = st.secrets.get("SERPAPI_API_KEY", "")
OUTPUT_FILE = "internet_contacts.csv"
PHONE_REGEX = r'(?:(?:\+44\s?|0)\s?(7[0-9]{2})\s?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3,4})'
EMAIL_REGEX = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

def serpapi_search(query: str, num_results: int = 10) -> List[dict]:
    """Search Google using SerpAPI."""
    if not SERPAPI_API_KEY:
        st.error("SerpAPI key not configured. Please add 'SERPAPI_API_KEY' to Streamlit secrets.")
        st.markdown("Get a key at [SerpAPI](https://serpapi.com).")
        return []

    params = {
        "engine": "google",
        "q": query,
        "api_key": SERPAPI_API_KEY,
        "num": num_results
    }
    try:
        logger.info(f"Executing SerpAPI query: {query}")
        response = requests.get("https://serpapi.com/search", params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        results = data.get("organic_results", [])
        logger.info(f"Found {len(results)} search results for query: {query}")
        return results
    except requests.RequestException as e:
        logger.error(f"Error fetching search results: {e}")
        st.error(f"Error fetching search results: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error during search: {e}")
        st.error(f"Unexpected error: {e}")
        return []

def extract_contacts(text: str) -> tuple[Set[str], Set[str]]:
    """Extract email addresses and phone numbers from text."""
    emails = set(re.findall(EMAIL_REGEX, text, re.IGNORECASE))
    phones_raw = re.findall(PHONE_REGEX, text, re.IGNORECASE)
    phones = set()
    for phone in phones_raw:
        # Normalize phone number: remove spaces, dashes, parentheses
        normalized = re.sub(r'[\s\-\(\)]', '', phone)
        # Convert to +44 format if it starts with 0
        if normalized.startswith('0'):
            normalized = '+44' + normalized[1:]
        phones.add(normalized)
    return emails, phones

def fetch_page_text(url: str) -> str:
    """Fetch and parse text from a webpage."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; ContactFinder/1.0; +https://example.com/bot)"
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        # Remove scripts, styles, and noscript tags
        for script_or_style in soup(["script", "style", "noscript"]):
            script_or_style.decompose()
        text = soup.get_text(separator=" ", strip=True)
        logger.info(f"Successfully fetched and parsed {url}")
        return text
    except requests.RequestException as e:
        logger.warning(f"Failed to fetch or parse {url}: {e}")
        return ""
    except Exception as e:
        logger.error(f"Unexpected error fetching {url}: {e}")
        return ""

def save_to_csv(contacts: List[dict], filename: str):
    """Save extracted contacts to a CSV file and provide download button."""
    if contacts:
        df = pd.DataFrame(contacts)
        df.to_csv(filename, index=False)
        logger.info(f"Saved {len(contacts)} contacts to {filename}")
        st.success(f"Saved {len(contacts)} contacts to {filename}")
        st.download_button(
            label="Download Contacts as CSV",
            data=df.to_csv(index=False).encode('utf-8'),
            file_name=filename,
            mime="text/csv"
        )
    else:
        logger.warning("No contacts found to save.")
        st.warning("No contacts found to save.")

def main():
    st.title("Internet Contact Finder")

    name = st.text_input("Full Name (required)", value="Sascha Riech")
    company = st.text_input("Company (optional)", "")
    num_results = st.slider("Number of search results", min_value=5, max_value=50, value=10)

    if st.button("Find Contacts"):
        if not name.strip():
            st.warning("Please enter a full name.")
            return

        query = f'"{name.strip()}"'
        if company.strip():
            query += f' "{company.strip()}"'
        query += " contact OR email OR phone site:*.uk"  # Focus on UK sites for mobile numbers

        st.info(f"Searching the internet for: {query}")
        results = serpapi_search(query, num_results=num_results)

        if not results:
            st.write("No search results found for your query.")
            return

        all_contacts = []
        st.write(f"Found {len(results)} search results. Extracting contacts...")

        for result in results:
            url = result.get("link")
            title = result.get("title", "No title")
            st.markdown(f"### [{title}]({url})")
            page_text = fetch_page_text(url)
            if not page_text:
                st.write("_Failed to fetch or parse page text._")
                continue

            emails, phones = extract_contacts(page_text)

            if emails or phones:
                for email in emails:
                    all_contacts.append({"url": url, "title": title, "email": email, "phone": ""})
                for phone in phones:
                    all_contacts.append({"url": url, "title": title, "email": "", "phone": phone})

                if emails:
                    st.write("Emails:", ", ".join(emails))
                else:
                    st.write("Emails: None found")
                if phones:
                    st.write("Mobile Phones:", ", ".join(phones))
                else:
                    st.write("Mobile Phones: None found")
            else:
                st.write("No contacts found on this page.")
            time.sleep(1)  # Avoid overwhelming servers

        if all_contacts:
            st.success("Summary of unique contacts found:")
            emails = sorted(set(contact["email"] for contact in all_contacts if contact["email"]))
            phones = sorted(set(contact["phone"] for contact in all_contacts if contact["phone"]))
            if emails:
                st.write("**Emails:**", ", ".join(emails))
            if phones:
                st.write("**Mobile Phones:**", ", ".join(phones))
            save_to_csv(all_contacts, OUTPUT_FILE)
        else:
            st.warning("No emails or mobile numbers found in the search results.")

if __name__ == "__main__":
    main()
