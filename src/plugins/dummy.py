from faff.core import PullPlugin, PushPlugin
import pendulum
from typing import Dict, List, Any

class DummyPlugin(PullPlugin, PushPlugin):
    def pull_plan(self, start: pendulum.Date, end: pendulum.Date, 
                  config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Fetches activities for a given day.

        Args:
            config (Dict[str, Any]): Configuration specific to the source.

        Returns:
            List[Dict[str, Any]]: List of activities formatted for Faff.
        """
        print("Fetching plan...")
        pass

    def push_timesheet(self, config: Dict[str, Any], timesheet: Dict[str, Any]) -> None:
        """
        Pushes a compiled timesheet to a remote repository.

        Args:
            config (Dict[str, Any]): Configuration specific to the destination.
            timesheet (Dict[str, Any]): The compiled timesheet to push.
        """
        print("Pushing timesheet...")
        pass