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
    # More flexible UK mobile number regex with spaces, dashes, parentheses
    pattern = re.compile(
        r"""
        (?:\+44\s?7\d{3}      # +44 7xxx
        |0\s?7\d{3}           # or 07xxx with optional space
        |\(?07\d{3}\)?)       # or (07xxx) with optional parentheses
        [\s\-]?\d{3}          # optional space/dash, 3 digits
        [\s\-]?\d{3,4}        # optional space/dash, 3 or 4 digits
        """,
        re.VERBOSE
    )

    matches = pattern.findall(text)
    normalized = set()
    for match in matches:
        phone = re.sub(r"[\s\-\(\)]", "", match)  # Remove spaces, dashes, parentheses
        if phone.startswith("07"):
            phone = "+44" + phone[1:]
        elif phone.startswith("0"):
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
        soup = BeautifulSoup(resp.text, "html.parser")
        for script_or_style in soup(["script", "style", "noscript"]):
            s


