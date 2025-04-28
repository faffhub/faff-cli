from tqdm import tqdm
from getpass import getpass # XXX: Maybe this too
import pendulum
import requests

from faff.cli.models import Activity, Plan
from faff.core.plugin import PullPlugin
from faff.core import TomlSerializer

class MyHoursPlugin(PullPlugin):

    def initialise_auth(self):
        # FIXME: Should this be using typer?
        print("Please enter your password to authenticate with MyHours.")
        print("This password will not be stored.")
        print(f"User: {self.config.get('email')}")

        LOGIN_API = "https://api2.myhours.com/api/tokens/login"

        body = {
            "granttype": "password",
            "email": self.config.get('email'),
            "password": getpass(),
            "clientId": "api"
        }

        data = requests.post(LOGIN_API, json=body)
        if data.status_code == 200:
            auth = {
                "access_token": data.json().get('accessToken'),
                "refresh_token": data.json().get('refreshToken'),
                "expires_in": data.json().get('expiresIn'),
                "expires_at": pendulum.now() + pendulum.Duration(
                    seconds=data.json().get('expiresIn'))
            }

            (self.state_path / 'token.toml').write_text(TomlSerializer.serialize(auth))
            return auth
        elif data.status_code == 401:
            raise ValueError("Invalid credentials. Please check your email and password.")
        else:
            raise ValueError("An error occurred during authentication.")

    def refresh_if_necessary(self, auth):
        if pendulum.now() > auth['expires_at'] - pendulum.Duration(minutes=5):
            print("Refreshing MyHours token...")
            REFRESH_API = "https://api2.myhours.com/api/tokens/refresh"
            body = {
                "granttype": "refresh_token",
                "refreshToken": auth['refresh_token']
            } 

            headers = {"Authorization": f"Bearer { auth['access_token'] }"}

            refresh = requests.post(REFRESH_API, json=body, headers=headers)
            if refresh.status_code == 200:
                new_auth = {
                    "access_token": refresh.json().get('accessToken'),
                    "refresh_token": refresh.json().get('refreshToken'),
                    "expires_in": refresh.json().get('expiresIn'),
                    "expires_at": pendulum.now("UTC") + pendulum.Duration(
                        seconds=refresh.json().get('expiresIn'))
                }

                (self.state_path / 'token.toml').write_text(TomlSerializer.serialize(new_auth))
                return new_auth
            elif refresh.status_code == 401:
                (self.state_path / 'token.toml').unlink(missing_ok=True)
                raise ValueError("Invalid refresh token. You will have to re-authenticate.")
            else:
                raise ValueError("An error occurred during token refresh.")
        else:
            # Token is still valid, no need to refresh
            return auth

    def authenticate(self):
        """
        Authenticate with MyHours API using the provided email and token.
        This method is a placeholder and should be implemented based on the
        specific authentication requirements of the MyHours API.
        """

        token_state_path = self.state_path / 'token.toml'
        try:
            import toml # FIXME: Agh
            loaded_toml = toml.loads(token_state_path.read_text())
            auth = {
                "access_token": loaded_toml.get('access_token'),
                "refresh_token": loaded_toml.get('refresh_token'),
                "expires_in": loaded_toml.get('expires_in'),
                "expires_at": pendulum.parse(loaded_toml.get('expires_at'))
            }

        except FileNotFoundError:
            auth = self.initialise_auth()

        auth = self.refresh_if_necessary(auth)

        return auth.get('access_token')

    def pull_plan(self, date: pendulum.Date) -> Plan:
        myhours_bearer_token = self.authenticate()
        headers = {"Authorization": f"Bearer { myhours_bearer_token }"}

        # Step 2: Fetch projects
        projects_resp = requests.get("https://api2.myhours.com/api/projects", headers=headers)
        projects_resp.raise_for_status()
        projects = projects_resp.json()

        activities = []
        for project in tqdm(projects):
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
