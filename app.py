import streamlit as st
import re
import requests
import logging
import pandas as pd
from ratelimit import limits, sleep_and_retry
from typing import List, Tuple
import time

# Try importing PyGithub, handle missing module
try:
    from github import Github, GithubException
except ModuleNotFoundError:
    st.error("The 'PyGithub' library is not installed. Please add 'PyGithub' to your requirements.txt file.")
    st.stop()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants
GITHUB_API_TOKEN = st.secrets.get("GITHUB_API_TOKEN", "")
RATE_LIMIT_CALLS = 5000  # GitHub API rate limit (5000/hour for authenticated users)
RATE_LIMIT_PERIOD = 3600  # 1 hour in seconds
EMAIL_REGEX = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
PHONE_REGEX = r'(\+44\s?|0)\s?(7[0-9]{2})\s?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3,4}'
OUTPUT_FILE = "github_contacts.csv"

@sleep_and_retry
@limits(calls=RATE_LIMIT_CALLS, period=RATE_LIMIT_PERIOD)
def github_api_call(func, *args, **kwargs):
    """Wrapper to handle GitHub API rate limiting and errors."""
    try:
        return func(*args, **kwargs)
    except GithubException as e:
        logger.error(f"GitHub API error: {e}")
        if e.status == 403:  # Rate limit exceeded
            logger.warning("Rate limit exceeded. Sleeping for 60 seconds.")
            time.sleep(60)
            st.error("GitHub API rate limit exceeded. Please try again later.")
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise

def extract_contacts(text: str) -> Tuple[List[str], List[str]]:
    """Extract email addresses and phone numbers from text."""
    emails = list(set(re.findall(EMAIL_REGEX, text, re.IGNORECASE)))
    phones_raw = re.findall(PHONE_REGEX, text, re.IGNORECASE)
    phones = list(set([re.sub(r'[\s\-\(\)]', '', phone[0] + phone[1]) for phone in phones_raw]))
    phones = [phone if phone.startswith('+44') else '+44' + phone[1:] if phone.startswith('0') else phone for phone in phones]
    return emails, phones

def search_repositories(query: str, github_client: Github) -> List[dict]:
    """Search GitHub repositories for a given query."""
    repos = []
    try:
        logger.info(f"Executing GitHub search query: {query}")
        search_results = github_api_call(github_client.search_repositories, query=query, sort="stars", order="desc")
        
        # Check if search_results is valid and has items
        if not search_results or search_results.totalCount == 0:
            logger.info(f"No repositories found for query: {query}")
            st.warning(f"No repositories found for query: {query}")
            return repos

        # Safely iterate over results, limiting to 10
        for repo in search_results.get_page(0)[:10]:  # Use get_page for pagination
            repos.append({
                "name": repo.full_name,
                "url": repo.html_url,
                "description": repo.description or ""
            })
        logger.info(f"Found {len(repos)} repositories for query: {query}")
    except GithubException as e:
        logger.error(f"GitHub API error during search: {e}")
        st.error(f"GitHub API error: {e.data.get('message', 'Unknown error')}")
    except IndexError as e:
        logger.error(f"Index error during repository search: {e}")
        st.error("Unexpected error processing search results. Please try a different query.")
    except Exception as e:
        logger.error(f"Unexpected error during search: {e}")
        st.error(f"Unexpected error: {e}")
    return repos

def scrape_repository(repo: dict, github_client: Github) -> List[dict]:
    """Scrape a single repository for contact information."""
    contacts = []
    repo_name = repo["name"]
    try:
        repository = github_api_call(github_client.get_repo, repo_name)
        
        # Check README
        try:
            readme = github_api_call(repository.get_readme)
            content = readme.decoded_content.decode("utf-8", errors="ignore")
            emails, phones = extract_contacts(content)
            for email in emails:
                contacts.append({"repo": repo_name, "url": repo["url"], "email": email, "phone": ""})
            for phone in phones:
                contacts.append({"repo": repo_name, "url": repo["url"], "email": "", "phone": phone})
        except GithubException:
            logger.warning(f"No README found for {repo_name}")

        # Check repository description
        emails, phones = extract_contacts(repo["description"])
        for email in emails:
            contacts.append({"repo": repo_name, "url": repo["url"], "email": email, "phone": ""})
        for phone in phones:
            contacts.append({"repo": repo_name, "url": repo["url"], "email": "", "phone": phone})

    except Exception as e:
        logger.error(f"Error scraping {repo_name}: {e}")
        st.error(f"Error scraping {repo_name}: {e}")
    return contacts

def save_to_csv(contacts: List[dict], filename: str):
    """Save extracted contacts to a CSV file."""
    if contacts:
        df = pd.DataFrame(contacts)
        df.to_csv(filename, index=False)
        logger.info(f"Saved {len(contacts)} contacts to {filename}")
        st.success(f"Saved {len(contacts)} contacts to {filename}")
        # Add download button for Streamlit Cloud
        st.download_button(
            label="Download Contacts as CSV",
            data=df.to_csv(index=False).encode('utf-8'),
            file_name="github_contacts.csv",
            mime="text/csv"
        )
    else:
        logger.warning("No contacts found to save.")
        st.warning("No contacts found to save.")

def main():
    st.title("GitHub Contact Finder")

    if not GITHUB_API_TOKEN:
        st.error("GitHub API token not configured. Please add 'GITHUB_API_TOKEN' to Streamlit secrets.")
        st.markdown("Generate a token at [GitHub Settings](https://github.com/settings/tokens) with 'repo' scope.")
        st.stop()

    # Validate GitHub API token
    try:
        github_client = Github(GITHUB_API_TOKEN)
        github_client.get_user().login  # Test token validity
    except GithubException as e:
        st.error(f"Invalid GitHub API token: {e.data.get('message', 'Unknown error')}")
        st.markdown("Generate a new token at [GitHub Settings](https://github.com/settings/tokens) with 'repo' scope.")
        st.stop()

    name = st.text_input("Full Name (required)", "")
    company = st.text_input("Company (optional)", "")

    if st.button("Find Contacts"):
        if not name.strip():
            st.warning("Please enter a full name.")
            return

        query = f'"{name.strip()}"'
        if company.strip():
            query += f' "{company.strip()}"'
        query += " in:readme in:description"

        st.info(f"Searching GitHub for: {query}")
        repos = search_repositories(query, github_client)

        if not repos:
            st.write("No repositories found for your query.")
            return

        all_contacts = []
        st.write(f"Found {len(repos)} repositories. Extracting contacts...")

        for repo in repos:
            st.markdown(f"### [{repo['name']}]({repo['url']})")
            contacts = scrape_repository(repo, github_client)
            if contacts:
                for contact in contacts:
                    if contact["email"]:
                        st.write(f"Email: {contact['email']}")
                    if contact["phone"]:
                        st.write(f"Mobile Phone: {contact['phone']}")
                all_contacts.extend(contacts)
            else:
                st.write("No contacts found in this repository.")
            time.sleep(1)  # Avoid overwhelming the API

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
