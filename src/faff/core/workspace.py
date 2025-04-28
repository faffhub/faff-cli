from functools import cache

from faff.core import FileSystem, LogFormatter, TomlSerializer
from faff.core.plugin import CompilePlugin, PullPlugin, PushPlugin
from faff.models import Activity, Config, Log, Plan

import tomllib
import pendulum
import importlib

from typing import Dict, List, Type
from slugify import slugify

class Workspace:

    def __init__(self):
        self.fs = FileSystem()
        self.config = Config.from_dict(tomllib.loads(self.fs.CONFIG_PATH.read_text()))

    def now(self) -> pendulum.DateTime:
        """
        Get the current time in the configured timezone
        """
        timezone = self.config.timezone
        return pendulum.now(timezone)

    def today(self) -> pendulum.Date:
        """
        Get today's date.
        """
        return pendulum.today().date()

    def parse_date(self, date: str) -> pendulum.Date:
        """
        Parse a date string into a pendulum.Date object.
        """
        try:
            return pendulum.parse(date).date()
        except ValueError:
            raise ValueError(f"Invalid date format: {date}. Expected YYYY-MM-DD.")

    @cache
    def get_plan_by_activity_id(self, activity_id: str, date: pendulum.Date) -> Plan:
        """
        Returns the plan for the given activity ID and date.
        """
        plans = self.get_plans(date)
        for plan in plans.values():
            for activity in plan.activities:
                if activity.id == activity_id:
                    return plan
        raise ValueError(f"Activity {activity_id} not found in plans for {date}.")

    @cache
    def get_activities(self, date: pendulum.Date) -> List[Activity]:
        """
        Returns a list of activities for the given date.
        """
        plans = self.get_plans(date).values()
        return {activity.id: activity
                for plan in plans
                for activity in plan.activities}

    @cache
    def get_plans(self, date: pendulum.Date) -> dict[str, Plan]:
        """
        Loads all plans from the `.faff/plans` directory under the given root,
        and returns those valid on the target date.

        A plan is valid if:
        - valid_from <= target_date
        - and (valid_until >= target_date or valid_until is None)
        """
        plans = {}
        # for file in self.fs.PLAN_PATH.glob("*.toml"):
        for file in self.fs.plan_files(date):
            plan = Plan.from_dict(tomllib.loads(file.read_text()))

            if plan.valid_from and plan.valid_from > date:
                continue
            if plan.valid_until and plan.valid_until < date:
                continue

            if plan.source not in plans.keys():
                plans[plan.source] = plan

            if plans.get(plan.source) and plans[plan.source].valid_from < plan.valid_from:
                plans[plan.source] = plan

        return plans

    def get_log(self, date: pendulum.Date) -> Log:
        """
        Returns the log for the given date.
        """
        log_path = self.fs.log_path(date)
        activities = self.get_activities(date)

        if log_path.exists():
            return Log.from_dict(tomllib.loads(log_path.read_text()), activities)
        else:
            return Log(date, self.config.timezone)

    def write_log(self, log: Log):
        """
        Writes the log to the file.
        """
        log_contents = LogFormatter.format_log(log, self.get_activities(log.date))
        log_filename = self.fs.log_path(log.date)
        with open(log_filename, "w") as f:
            f.write(log_contents)

    def start_timeline_entry(self, activity_id: str, note: str) -> str:
        """
        Start a timeline entry for the given activity, stopping any previous one.
        """
        log = self.get_log(self.today())
        now = self.now()

        activities = self.get_activities(self.today())

        if activity_id not in activities:
            return f"Activity {activity_id} not found in today's plan."

        activity = activities[activity_id]
        log = log.start_timeline_entry(activity, now, note)

        self.write_log(log)
        return f"Started logging for activity {activity_id} at {now.to_time_string()}."

    def stop_timeline_entry(self) -> str:
        """
        Stop the most recent ongoing timeline entry.
        """
        target_date = self.today()
        log = self.get_log(target_date)
        now = self.now()

        active_entry = log.active_timeline_entry()
        if active_entry:
            self.write_log(log.stop_active_timeline_entry(now))
            return f"Stopped logging for activity {active_entry.activity.name} at {now.to_time_string()}."

        return "No ongoing timeline entries found to stop."

    def _plugin_instances(self, cls, configs):
        plugins = self._load_plugins()
        instances = {}

        for plugin_config in configs:
            plugin_str = plugin_config.get("plugin")
            Plugin = plugins.get(plugin_str)
            if not Plugin:
                raise ValueError(
                    f"Plugin {plugin_str} not found in configuration.")
            if not issubclass(Plugin, cls):
                raise ValueError(
                    f"Plugin {plugin_str} is not an {cls}.")
            if plugin_config.get('name') in instances.keys():
                raise ValueError(
                    f"Duplicate source name {plugin_config.get('name')} found in configuration.")
            instances[plugin_config.get('name')] = Plugin(plugin=plugin_config.get("plugin"),
                                                   name=plugin_config.get("name"),
                                                   config=plugin_config.get("config"),
                                                   state_path=self.fs.PLUGIN_STATE_PATH / slugify(plugin_config.get("name")))

        return instances

    def compilers(self):
        """
        Returns the configured compilers
        """
        # FIXME: This duplication still feels gross
        return self._plugin_instances(CompilePlugin, self.config.compilers)

    def plan_sources(self):
        """
        Returns the configured plan sources
        """
        return self._plugin_instances(PullPlugin, self.config.plan_sources)

    def write_plan(self, pull_plugin: PullPlugin, date: pendulum.Date) -> None:
        """
        Writes the plan for the given date.
        """
        plan = pull_plugin.pull_plan(date)

        path = self.fs.PLAN_PATH / pull_plugin.filename(date)

        path.write_text(TomlSerializer.serialize(plan))

    def _load_plugins(self) -> Dict[str, Type]:
        plugins = {}

        for plugin_file in self.fs.PLUGIN_PATH.glob("*.py"):
            if plugin_file.name == "__init__.py":
                continue

            module_name = f"plugins.{plugin_file.stem}"
            spec = importlib.util.spec_from_file_location(module_name, plugin_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, type) and (
                    issubclass(attr, (PullPlugin, PushPlugin, CompilePlugin))
                ) and attr not in (PullPlugin, PushPlugin):
                    plugins[plugin_file.stem] = attr  # Store the class

        return plugins