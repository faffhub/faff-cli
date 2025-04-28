from faff.cli.models import Log, Timesheet
from faff.core.plugin import CompilePlugin

class TargetCompiler(CompilePlugin):
    """
    A plugin that compiles a user's private log to an Element timesheet.
    Changing the objective of this temporarily. Right now this plugin should 
    implement the policy as it is currently defined:
    - Any client-billable work should be billed as a half or full day?
    """

    def compile_time_sheet(self, log: Log) -> Timesheet:
        activities = filter(log.timeline)

        target = self.config.get("target")

        print(self.config)
        print(activities)