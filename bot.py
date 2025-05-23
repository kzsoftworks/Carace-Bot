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
BOARD_IDS = [106]  # Replace with your actual board IDs

# Set up Jira API session
headers = {
    # Corrected: no extra "Basic " prefix here, requests.auth._basic_auth_str returns full header string
    "Authorization": requests.auth._basic_auth_str(JIRA_EMAIL, JIRA_API_TOKEN),
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
if (week_number+1) % 2 != 0:
    msg = f"🛑 Week {week_number} is not a demo week — skipping Jira summary."
    print(msg)
    sys.exit(0)

completed_stories_by_user = {}
crct_stories_by_user = {}

for board_id in BOARD_IDS:
    board_name = f"Board {board_id}"

    # Get active sprints
    res = requests.get(f"{jira_api_base}/board/{board_id}/sprint?state=active", headers=headers)
    print(f"Request URL: {res.url}")
    print(f"Response status code: {res.status_code}")
    print(f"Response text: {res.text[:500]}")
    sprints = res.json().get("values", [])
    
    if not sprints:
        msg = f"📭 No active sprint found for board: *{board_name}*"
        print(msg)
        post_to_slack(msg)
        continue

    active_sprint = sprints[0]
    sprint_id = active_sprint["id"]
    print(f"Response sprints: {sprint_id}")
    # Get issues in the active sprint
    start_at = 0
    while True:
        res = requests.get(
            f"{jira_api_base}/sprint/{sprint_id}/issue?startAt={start_at}",
            headers=headers
        )
        print(f"Request URL: {res.url}")
        print(f"Response status code: {res.status_code}")
        print(f"Response text: {res.text[:500]}")
        issues_data = res.json()
        issues = issues_data.get("issues", [])
        total = issues_data.get("total", 0)
        
        for issue in issues:
            fields = issue.get("fields", {})
            issuetype = fields.get("issuetype", {}).get("name", "")
            status = fields.get("status", {}).get("name", "")
            assignee = fields.get("assignee")
            assignee_name = assignee.get("displayName", "Unassigned") if assignee else "Unassigned"

            print(f"Response Assignee: {assignee_name}")
            print(f"Response issuetype: {issuetype}")
            print(f"Response status: {status.lower()}")

            if issuetype == "Story":
                status_lower = status.lower()
                
                if status_lower in ["dev-complete", "test-pending", "test-blocked", "done", "deployed"]:
                    if assignee_name not in completed_stories_by_user:
                        completed_stories_by_user[assignee_name] = []
                    completed_stories_by_user[assignee_name].append(issue["key"])
                
                elif status_lower in ["code review", "code-test"]:
                    if assignee_name not in crct_stories_by_user:
                        crct_stories_by_user[assignee_name] = []
                    crct_stories_by_user[assignee_name].append(issue["key"])

        if total-start_at <+ 0:
            break
        start_at += 50
        print(f"Response issues_data: {start_at}")

if not completed_stories_by_user and not crct_stories_by_user:
    msg = "📦 No completed *Story* issues found in any active sprint this demo week."
    print(msg)
    post_to_slack(msg)
    sys.exit(0)

print(f"📊 *Sprint Summary")
summary = "📊 *Completed Stories*\n\n"
for user, issues in sorted(completed_stories_by_user.items(), key=lambda x: x[1][0]):
    summary += f"• *{user}*: {', '.join([f'<https://{JIRA_DOMAIN}/browse/{key}|{key}>' for key in issues])}\n"

summary2 = "📊 *CR/CT Stories*\n\n"
for user, issues in sorted(crct_stories_by_user.items(), key=lambda x: x[1][0]):
    summary2 += f"• *{user}*: {', '.join([f'<https://{JIRA_DOMAIN}/browse/{key}|{key}>' for key in issues])}\n"


print(summary)
print(summary2)
post_to_slack(summary)
post_to_slack(summary2)