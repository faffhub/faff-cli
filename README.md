faff init
faff config

We have a faff pipeline, which comprises:
- a source of work
- the private log
- a compiler to translate that log into a timesheet suitable for the target audience
- a identity with which that timesheet can be signed
- a faff recipient to receive the signed timesheet

We have a bridged pipeline, which comprises:
- a source of work
- the private log
- a compiler to translate that log into a timesheet suitable for the target audience
- a bridge to the legacy system

In perhaps both cases we might want to track the state of the timesheet. We would want to know when it had been successfully sent.


faff init
Initialise a faff repo in the current directory.

faff config
Open faff configuration file in default editor.

faff status
Show a quick status report of the faff repo and today's private log.

faff start
Start recording time against an activity now.

faff stop
Stop the current activity.

faff log list 
List all the private log entries, with a summary of the hours recorded that day.

faff log show <date>
Print the specified private log to stdout.

faff log edit <date>
Edit the specified private log in the default editor.

faff log rm <date>
Delete the specified private log.

faff log refresh <date>
Roundtrip the private log file to ensure file is properly formatted.

faff id list
List the configured ids.

faff id create <name>
Create a new id with the specified name.

faff id rm <name>
Delete the specified id (public and private key).

faff source list
List the configured work sources.

faff source pull

faff plan list <date>
List the plans effective on the specified date.

faff plan show <date>
faff plan show --source <source>
faff plan show --id <id>
Show the activities on plan on the specified date.