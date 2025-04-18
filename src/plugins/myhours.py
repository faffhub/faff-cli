import pendulum
import requests

from faff.core import PullPlugin
from faff.models import Plan, Activity

class MyHoursPlugin(PullPlugin):

    def pull_plan(self, date: pendulum.Date) -> Plan:
        myhours_url = "https://api2.myhours.com/api/Projects"
        myhours_email = self.config.get('email')
        myhours_token = self.config.get('token')

        headers = {"Authorization": f"Bearer { myhours_token }"}

        # Step 2: Fetch projects
        projects_resp = requests.get("https://api2.myhours.com/api/projects", headers=headers)
        projects_resp.raise_for_status()
        projects = projects_resp.json()

        activities = []
        for project in projects:
            print("p")
            tasks_resp = requests.get(f"https://api2.myhours.com/api/projects/{project['id']}/tasklist", headers=headers)
            tasks_resp.raise_for_status()
            tasklist = tasks_resp.json()

            def collect_tasks(bucket: str):
                return tasklist[0].get(bucket, []) if tasklist else []

            all_tasks = (
                collect_tasks("incompletedTasks") +
                collect_tasks("completedTasks") +
                collect_tasks("archivedTasks")
            )

            for task in all_tasks:
                print("t")
                activities.append(Activity(
                    id=f"myhours-{task['id']}",
                    name=f"{project['name']} → {task['name']}",
                    meta={
                        "project": project["name"],
                        "project_id": project["id"],
                        "completed": task["completed"],
                        "archived": task["archived"],
                        "rate": task.get("rate"),
                    }
                ))

        return Plan(
            source="myhours",
            valid_from=date,
            valid_until=None,
            activities=activities
        )
