import os
import requests
import datetime
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# === CONFIGURATION ===
JIRA_DOMAIN = os.getenv("JIRA_DOMAIN")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_CHANNEL_ID = os.getenv("SLACK_CHANNEL_ID")

JIRA_HEADERS = {
    "Authorization": f"Basic {requests.auth._basic_auth_str(JIRA_EMAIL, JIRA_API_TOKEN)}",
    "Accept": "application/json"
}

client = WebClient(token=SLACK_BOT_TOKEN)


def get_all_jira_boards():
    boards = []
    start_at = 0
    max_results = 50

    while True:
        url = f"https://{JIRA_DOMAIN}/rest/agile/1.0/board?startAt={start_at}&maxResults={max_results}"
        response = requests.get(url, headers=JIRA_HEADERS)
        response.raise_for_status()
        data = response.json()
        boards.extend(data.get("values", []))

        if data.get("isLast", True) or len(data.get("values", [])) == 0:
            break

        start_at += max_results

    return boards


def get_completed_stories_in_active_sprint(board_id):
    jql = 'issuetype=Story AND status=Complete AND Sprint in openSprints() AND resolved >= -7d'
    url = f"https://{JIRA_DOMAIN}/rest/agile/1.0/board/{board_id}/issue?jql={jql}&maxResults=100"
    response = requests.get(url, headers=JIRA_HEADERS)
    response.raise_for_status()
    issues = response.json().get("issues", [])

    results = []
    for issue in issues:
        fields = issue.get("fields", {})
        assignee = fields.get("assignee")
        if assignee:
            results.append((assignee.get("displayName"), issue["key"]))

    return results


def compile_weekly_summary():
    boards = get_all_jira_boards()
    summary = {}

    for board in boards:
        try:
            completed_stories = get_completed_stories_in_active_sprint(board["id"])
            for assignee, issue_key in completed_stories:
                summary.setdefault(assignee, []).append(issue_key)
        except Exception as e:
            print(f"Failed to fetch from board {board['id']} ({board['name']}): {e}")

    return summary


def send_slack_message(summary):
    if not summary:
        text = "📦 No completed stories found in active sprints this week."
    else:
        text = "*📦 Weekly Jira Summary (Completed Stories in Active Sprints)*\n\n"
        for assignee, issues in summary.items():
            text += f"*{assignee}*: {', '.join(issues)}\n"

    try:
        client.chat_postMessage(channel=SLACK_CHANNEL_ID, text=text)
    except SlackApiError as e:
        print(f"Error sending message to Slack: {e.response['error']}")


if __name__ == "__main__":
    today = datetime.datetime.today()
    if today.weekday() == 4:  # Friday
        summary = compile_weekly_summary()
        send_slack_message(summary)
    else:
        print("Not Friday — skipping execution.")
