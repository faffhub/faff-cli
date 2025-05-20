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
Start recording time against an bucket now.

faff stop
Stop the current bucket.

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
Show the buckets on plan on the specified date.

Notes:

I think the template idea has legs.

A record has:
- an intent
- qualitative data

An intent, fully expressed, has:
- a role
- an activity
- a goal
- a beneficiary

In truth, a role can have _one or more_ roles, goals, or beneficiaries. But that feels like it's going too far - you should jus tpick the main one.

A template might have a role, a goal, an activity, but an empty beneficiary - something like a "1:1" template would be the same RAG but switch in a different B.

A template might have a role, a goal, and a beneficiary but an empty activity - something like "Adfinis Machine" template woudl always have the same RGB but you'd switch in a A.

Mapping to a bucket is a different matter. It's _really_ the job of the compiler, but a next-to-impossible one without a hint.

For templates, you'd want to be able to pick a template then sub in the variable, but the variable should also be pre-populated and if pre-existing should re-use an historic bucket association.


faff start
I am doing: 1:1s [TEMPLATE] (for: ben, emma, arthur, ... )
            Building the Adfinis Machine [TEMPLATE] (action: prep, something, something... )
            NSDR [TEMPLATE] (action: prep, run, minute)
            Monday Sync
            CS Role Review