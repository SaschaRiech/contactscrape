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
# Use original ChatGPT phone regex for consistency
PHONE_REGEX = r'(?:\+44\s?7\d{3}|0\s?7\d{3}|\(?07\d{3}\)?)\s?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3,4}'
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

# Alternative using googlesearch (uncomment to use if no SerpAPI key)
"""
try:
    from googlesearch import search
except ModuleNotFoundError:
    st.error("The 'googlesearch-python' library is not installed. Please add 'googlesearch-python' to your requirements.txt file.")
    st.stop()

def serpapi_search(query: str, num_results: int = 10) -> List[dict]:
    results = []
    try:
        logger.info(f"Executing Google search query: {query}")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        for url in search(query, num_results=num_results, pause=3.0):
            results.append({"link": url, "title": url})
        logger.info(f"Found {len(results)} search results for query: {query}")
        return results
    except Exception as e:
        logger.error(f"Error fetching search results: {e}")
        st.error(f"Error fetching search results: {e}. Google may be blocking the request.")
        return []
"""

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
        if normalized.startswith('+447') or normalized.startswith('07'):  # Validate UK mobile
            phones.add(normalized)
    logger.debug(f"Extracted {len(emails)} emails and {len(phones)} phones from text")
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
        logger.debug(f"Page text (first 500 chars): {text[:500]}")
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
    restrict_uk = st.checkbox("Restrict to UK websites (site:*.uk)", value=False)

    if st.button("Find Contacts"):
        if not name.strip():
            st.warning("Please enter a full name.")
            return

        query = f'"{name.strip()}"'
        if company.strip():
            query += f' "{company.strip()}"'
        query += " contact OR email OR phone"
        if restrict_uk:
            query += " site:*.uk"

        st.info(f"Searching the internet for: {query}")
        results = serpapi_search(query, num_results=num_results)

        if not results:
            st.write("No search results found for your query. Try broadening the search (e.g., remove 'site:*.uk' or change the name).")
            return

        all_contacts = []
        st.write(f"Found {len(results)} search results. Extracting contacts...")

        for result in results:
            url = result.get("link")
            title = result.get("title", url)
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
            st.warning("No emails or mobile numbers found in the search results. Try a different query or uncheck 'Restrict to UK websites'.")

if __name__ == "__main__":
    main()
