import os
import json
import sys
import logging
import requests
from dotenv import load_dotenv

# import repomix # Removed for now
# from langchain_openai import ChatOpenAI # Removed for now


def main():
    logging.basicConfig(level=logging.INFO)
    load_dotenv()

    event_path = os.getenv("GITHUB_EVENT_PATH")
    if not event_path or not os.path.exists(event_path):
        logging.error("GITHUB_EVENT_PATH is not set or file does not exist.")
        sys.exit(1)

    with open(event_path) as f:
        event = json.load(f)
        # Correct logging format: Use %s for string formatting or f-strings
        logging.info("--- FULL GITHUB EVENT PAYLOAD ---")
        logging.info("%s", json.dumps(event, indent=2))
        logging.info("--- END GITHUB EVENT PAYLOAD ---")

    pr = event.get("pull_request", {})
    pr_number = pr.get("number")
    repository_info = event.get("repository", {})
    repository = repository_info.get("full_name")
    repo_owner = repository_info.get("owner", {}).get("login")
    repo_name = repository_info.get("name")
    base_sha = pr.get("base", {}).get("sha")
    head_sha = pr.get("head", {}).get("sha")
    clone_url = repository_info.get("clone_url") # Needed if repomix clones

    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        logging.error("GITHUB_TOKEN environment variable not set. Cannot proceed.")
        sys.exit(1)

    # Fetch PR details
    pr_details = None
    if repository and pr_number:
        pr_url = f"https://api.github.com/repos/{repository}/pulls/{pr_number}"
        logging.info(f"Fetching PR details from: {pr_url}")
        try:
            resp = requests.get(
                pr_url,
                headers={"Authorization": f"Bearer {github_token}", "Accept": "application/vnd.github.v3+json"}
            )
            resp.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
            pr_details = resp.json()
            logging.info("--- PR DETAILS ---")
            logging.info("%s", json.dumps(pr_details, indent=2))
            logging.info("--- END PR DETAILS ---")
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to fetch PR details: {e}")
            # Decide if you want to exit or continue without PR details
            # sys.exit(1)
    else:
        logging.warning("Could not determine repository or PR number from event payload.")


    # Fetch list of files changed in the PR:
    changed_files = None
    if repository and pr_number:
        files_url = f"https://api.github.com/repos/{repository}/pulls/{pr_number}/files"
        logging.info(f"Fetching changed files list from: {files_url}")
        try:
            resp = requests.get(
                files_url,
                headers={
                    "Authorization": f"Bearer {github_token}", # Use the variable defined earlier
                    "Accept": "application/vnd.github.v3+json"
                }
            )
            resp.raise_for_status()
            changed_files = resp.json()
            logging.info("--- CHANGED FILES ---")
            logging.info("%s", json.dumps(changed_files, indent=2))
            logging.info("--- END CHANGED FILES ---")
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to fetch changed files: {e}")
            # Decide if you want to exit or continue
            # sys.exit(1)
    else:
        # This condition is likely already handled above, but added for safety
        logging.warning("Could not determine repository or PR number for fetching files.")


    # TODO: Get the actual code diffs for the changed files
    # This typically involves using the 'patch' field from the changed_files response
    # or fetching the diff using the base and head SHAs.
    logging.info("--- CODE DIFF (Placeholder) ---")
    if changed_files:
        for file_info in changed_files:
            filename = file_info.get('filename')
            patch = file_info.get('patch')
            status = file_info.get('status')
            logging.info(f"File: {filename} (Status: {status})")
            if patch:
                 # Log only a snippet or confirmation, as patches can be large
                 logging.info(f"  Patch available ({len(patch)} bytes)")
                 # logging.debug(f"Patch:\n{patch}") # Use debug level for full patch
            else:
                 logging.info("  No patch data available in this response.")
    else:
        logging.info("No changed file information available to extract diffs.")
    logging.info("--- END CODE DIFF (Placeholder) ---")


    # Removed Repomix, SRS/SDD loading, LangChain, and comment posting sections

    logging.info(f"Finished basic processing for PR #{pr_number} in {repository}")


if __name__ == "__main__":
    main()
# This line is removed by the previous REPLACE block
