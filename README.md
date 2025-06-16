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
Start recording time against an intent now.

faff stop
Stop the current intent.

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
Show the plan on the specified date.

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

Mapping to a tracker is a different matter. It's _really_ the job of the compiler, but a next-to-impossible one without a hint.

For templates, you'd want to be able to pick a template then sub in the variable, but the variable should also be pre-populated and if pre-existing should re-use an historic tracker association.


faff start
I am doing: 1:1s [TEMPLATE] (for: ben, emma, arthur, ... )
            Building the Adfinis Machine [TEMPLATE] (action: prep, something, something... )
            NSDR [TEMPLATE] (action: prep, run, minute)
            Monday Sync
            CS Role Review


faff start

? What are you doing?

1. Type an _activity_.
   At the very least, you want to record that you are working on an activity. If you have used
   an activity before, we should suggest matches here.
   Examples of activities include:
    - reading email
    - writing a document
    - reviewing a proposal
    - strategic thinking
    - a URL to a Jira task, or the name of task
    - working on project X, or sub-project X.1 
2. Type an _intent_.
   An intent is richer than an activity. It represents everything you _should_ be tracking when
   you track time (role, activity, goal, beneficiary), and everything you need to map it to legacy
   time-tracking systems.
3. Our goal is to record intents, but folks won't always have the time or energy to do this inline.


It seems obvious at this second that I would achieve all of this by:

- answering the question "what are you doing?"
- hmm, the epiphany evaporated
- it was going to be something like "and if you're reusing an old intent with a new activity or beneficiary, then you can turn it into a template then", but you'd probably need to rename it, too
- maybe, if you've got a _nearly_ right intent, something like "preparing for NSDR", you could:
    - choose it
    - see the associated intent
    - say "yes, no, or tweak"
    - if you tweak, you can tweak either the activity or the beneficiary
    - in doing so, you create a template
- then in future, if you choose a _template_ rather than a straight intent, you'll be:
    - given the list of all the values you've previously put into the template as quick options
        - press Esc to see all options or add a new one
        - you shouldn't be able to add a new one directly from the shortlist, because you might roll a brand new beneficiary
          when there's already a suitable entity

Separate problem - I'm making entities like "element/juhol" but those are _not_ coming from Element - they're local. So should they be
local/element/juhol?

? What are you doing?
> Create new: 1:1 with Juho
? What job role are you playing in this activity?
> Head of Customer Success (element/head-of-customer-success)
? What action are you doing?
> 1:1 (element/1:1)
? What's the main goal of this activity?
> Resolving Operational Issues (element/resolving-operational-issues)
? Who or what is this for or about?
> element/staff/juho
? Are there any trackers to associate?
> Admin (myhours/12345)
? Any more?


? What are you doing?
> 1:1 with Juho
? Are these details still correct:
- Role:       Head of Customer Succes (element/head-of-customer-success)
- Objective:  Resolving Operational Issues (element/resolving-operational-issues)
- Action:     1:1 (element/1:1)
- Subject:    Juho (element/staff/juho)
- Trackers:   Admin (myhours/12345)

titlecase

? What job role are you playing in this activity?
> Default: Head of Customer Success (element/head-of-customer-success)
? What action are you doing?
> Default: 1:1 (element/1:1)
? What's the main goal of this activity?
> Default: Resolving Operational Issues (element/resolving-operational-issues)
? Who or what is this for or about?
> element/staff/juho
? Are there any trackers to associate?
> Admin (myhours/12345)
? Any more?

? Are these details still correct?




New question - how do we store trackers?
I'm trying to cut down on their complexity now - they're just an identifier and a name.

So in the plan, they could be 