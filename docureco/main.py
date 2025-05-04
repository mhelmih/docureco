import os
import json
import sys
import logging
import requests
from dotenv import load_dotenv

# from langchain import OpenAI
# import repomix


def main():
    logging.basicConfig(level=logging.INFO)
    load_dotenv()

    event_path = os.getenv("GITHUB_EVENT_PATH")
    if not event_path or not os.path.exists(event_path):
        logging.error("GITHUB_EVENT_PATH is not set or file does not exist.")
        sys.exit(1)

    with open(event_path) as f:
        event = json.load(f)

    pr = event.get("pull_request", {})
    pr_number = pr.get("number")
    repository = event.get("repository", {}).get("full_name")
    
    print(pr)

    # TODO: compute code changes (e.g., using Repomix)
    # changes = repomix.diff()

    # TODO: load SRS and SDD files
    # with open('path/to/SRS.md') as f: ...

    # TODO: generate recommendations via LangChain/OpenAI
    # llm = OpenAI(temperature=0)
    # ...

    # TODO: post recommendations to GitHub PR
    # use GITHUB_TOKEN and GitHub API

    # Simple test: post a comment to the PR to confirm the agent is working
    github_token = os.getenv("GITHUB_TOKEN")
    if github_token:
        comment = "✅ Docureco agent is up and running."
        headers = {
            "Authorization": f"Bearer {github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        url = f"https://api.github.com/repos/{repository}/issues/{pr_number}/comments"
        resp = requests.post(url, json={"body": comment}, headers=headers)
        if resp.ok:
            logging.info("Posted test comment to PR")
        else:
            logging.error(f"Failed to post test comment: {resp.status_code} {resp.text}")
    else:
        logging.warning("GITHUB_TOKEN not set; skipping test comment")

    logging.info(f"Processed PR #{pr_number} in {repository}")


if __name__ == "__main__":
    main()
