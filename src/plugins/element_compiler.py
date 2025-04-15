from faff.core import CompilePlugin
from faff.models import TimeSheet, Log

class ElementCompiler(CompilePlugin):
    """
    A plugin that compiles a user's private log to an Element timesheet.
    We want to include:
    - Everything that can be matched to a MyHours bucket
    - We don't want to manipulate the data beyond this particularly - we _will_
    - want to build Element-side postprocessors that turn this data in BWI data,
    - maintenance vs development data, per customer support cost data, and R&D
    - tax credit reports.
    - These need to be identified with an Element ID, and signed with an Element-
    - recognised signature.
    """

    def compile_time_sheet(self, log: Log) -> TimeSheet:
        activities = log.activities



        pass