import pendulum
import requests
from requests.auth import HTTPBasicAuth

from faff.core import PullPlugin
from faff.models import Plan, Activity

class JiraPlugin(PullPlugin):

    def pull_plan(self, date: pendulum.Date) -> Plan:
        jira_base_url = self.config.get('url')
        jira_email = self.config.get('email')
        jira_token = self.config.get('api_token')

        auth = HTTPBasicAuth(jira_email, jira_token)

        # Fetch Jira issues
        issues = self.fetch_jira_issues(jira_base_url, jira_email, auth, pendulum.today(),
                                        pendulum.tomorrow())

        activities = [Activity(id=f"jira-element-{issue.get('key')}",
                               name=issue.get('fields', {}).get('summary'))
                      for issue in issues]
        return Plan(source="jira",
                    valid_from=date,
                    valid_until=date,
                    activities=activities)

    def build_jql_assigned_during(self, username: str, start, end) -> str:
        """
        Build a JQL query string for issues where a user was assignee during a date range.
        
        Args:
            username (str): Jira username/login (usually email).
            start (datetime/date): Inclusive start date.
            end (datetime/date): Exclusive end date.
        
        Returns:
            str: JQL query string.
        """
        start_str = pendulum.instance(start).format("YYYY/MM/DD")
        end_str = pendulum.instance(end).format("YYYY/MM/DD")
        
        return f'assignee was "{username}" AND status was "in progress" DURING ("{start_str}", "{end_str}")'


    def fetch_jira_issues(self, base_url, jira_email, auth,
                          start_date, end_date, max_results=1000):
        """Fetch issues from a Jira project."""
        url = f"{base_url}/rest/api/2/search"

        # Example usage
        jql = self.build_jql_assigned_during(jira_email, start_date, end_date)

        all_issues = []
        start_at = 0

        while True:
            query = {
                "jql": jql,
                "startAt": start_at,
                "maxResults": 50,
                "fields": "key,issuetype,summary,parent"
            }

            response = requests.get(url, params=query, auth=auth)
            response.raise_for_status()  # Raise an error for HTTP issues
            data = response.json()

            issues = data.get("issues", [])
            all_issues.extend(issues)

            if len(issues) < 50:
                break

            start_at += 50

        return all_issues
