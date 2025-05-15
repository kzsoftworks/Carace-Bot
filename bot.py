import os
import sys
import datetime
import requests
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# Env variables
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_DOMAIN = os.getenv("JIRA_DOMAIN")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_CHANNEL_ID = os.getenv("SLACK_CHANNEL_ID")

# Set up Jira API session
headers = {
    "Authorization": f"Basic {requests.auth._basic_auth_str(JIRA_EMAIL, JIRA_API_TOKEN)}",
    "Accept": "application/json"
}
jira_api_base = f"https://{JIRA_DOMAIN}/rest/agile/1.0"

# Set up Slack client
slack_client = WebClient(token=SLACK_BOT_TOKEN)

def post_to_slack(message):
    try:
        slack_client.chat_postMessage(channel=SLACK_CHANNEL_ID, text=message)
        print("✅ Message posted to Slack.")
    except SlackApiError as e:
        print(f"❌ Slack error: {e.response['error']}")

# Skip if not a demo week
week_number = datetime.date.today().isocalendar().week
if week_number % 2 != 0:
    msg = f"🛑 Week {week_number} is not a demo week — skipping Jira summary."
    print(msg)
    post_to_slack(msg)
    sys.exit(0)

# Get all boards
print("📋 Fetching Jira boards...")
boards = []
start_at = 0
while True:
    res = requests.get(f"{jira_api_base}/board?startAt={start_at}", headers=headers)
    data = res.json()
    boards.extend(data.get("values", []))
    if data.get("isLast", True):
        break
    start_at += data.get("maxResults", 50)

print(f"✅ Found {len(boards)} boards.")

completed_stories_by_user = {}

for board in boards:
    board_id = board["id"]
    board_name = board["name"]

    # Get active sprints
    res = requests.get(f"{jira_api_base}/board/{board_id}/sprint?state=active", headers=headers)
    sprints = res.json().get("values", [])

    if not sprints:
        msg = f"📭 No active sprint found for board: *{board_name}*"
        print(msg)
        post_to_slack(msg)
        continue

    active_sprint = sprints[0]
    sprint_id = active_sprint["id"]

    # Get issues in the active sprint
    start_at = 0
    while True:
        res = requests.get(
            f"{jira_api_base}/sprint/{sprint_id}/issue?startAt={start_at}",
            headers=headers
        )
        issues_data = res.json()
        issues = issues_data.get("issues", [])

        for issue in issues:
            fields = issue.get("fields", {})
            issuetype = fields.get("issuetype", {}).get("name", "")
            status = fields.get("status", {}).get("name", "")
            assignee = fields.get("assignee", {})
            assignee_name = assignee.get("displayName", "Unassigned")

            if issuetype == "Story" and status.lower() == "complete":
                if assignee_name not in completed_stories_by_user:
                    completed_stories_by_user[assignee_name] = []
                completed_stories_by_user[assignee_name].append(issue["key"])

        if issues_data.get("isLast", True):
            break
        start_at += issues_data.get("maxResults", 50)

# Handle case: no completed stories found
if not completed_stories_by_user:
    msg = "📦 No completed *Story* issues found in any active sprint this demo week."
    print(msg)
    post_to_slack(msg)
    sys.exit(0)

# Build summary
summary = "📊 *Biweekly Jira Summary – Completed Stories*\n\n"
for user, issues in completed_stories_by_user.items():
    summary += f"• *{user}*: {', '.join(issues)}\n"

print(summary)
post_to_slack(summary)
