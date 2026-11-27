# Install from an existing coding agent

You are the setup agent in the user's existing Claude Code, Codex
or OpenCode session. The request is to set up this workflow here, including Orca
when missing. Orca is needed to run the workflow, not to begin its installation.

1. Read the target repository's instructions and Git status. Preserve existing
   work. Keep this agent as coordinator while setting up dependencies; do not
   start a second coding session just to install the workflow.
2. Obtain the `setup-orca-workflow` skill. If already installed, read its actual
   `SKILL.md`. Otherwise, when Node/npm is available, run the Skills CLI in project
   scope with `--skill setup-orca-workflow --copy` for the user's current agent.
   If Node/npm is absent, prefer cloning this repository into a system-temp
   folder outside the target and reading `skills/setup-orca-workflow/SKILL.md`
   there; a local checkout works without installing a skill or Node. Do not copy
   the entire starter repository into the application or change global skills.
3. Ensure uv (including uvx), Git and a Python 3.11+ interpreter are available for the skill helper.
   Use existing compatible installations; install missing prerequisites through
   the platform's official/package-manager methods within the requested setup.
   Use the chosen interpreter explicitly if the system `python3` is older. On
   Windows, `python3` is often a Microsoft Store placeholder: use `py -3` or the
   installed `python.exe`, and use `winget` (`Python.Python.3.12`, `StablyAI.Orca`,
   `Docker.DockerDesktop`) where available. A missing prerequisite is setup work
   for the agent, not a reason to hand the user another manual tutorial.
4. Distinguish the current setup agent from the future task coordinator. OpenCode
   can perform setup, but the kit's enabled task-coordinator profiles are currently
   Claude/Codex and implementation requires Claude Code. Resolve missing clients
   and real account preferences; do not silently claim an unavailable template
   provider is ready or enable unsupported worker profiles.
5. Follow the skill completely. Bootstrap Orca and preview the published install with
   `uvx orca-agent-workflow@0.2.0 init`. Repeat with `--apply`, merge custom
   instructions, configure project checks/runtime, and validate the result. The
   helper's bootstrap plans by default; `bootstrap --apply` performs its supported
   Orca installation/startup steps when this is within the user's request.
6. Handle steps with your tools when possible. Ask the user only for actual system
   permissions, first-launch choices, sign-in or material preferences you cannot
   resolve. Resume the installation afterward. Never bypass OS security, invent
   credentials, reset unrelated work or claim unverified checks passed.
7. Show concrete adoption changes and actual verification. Follow the project's
   commit/PR authorization and leave merge to the user. Retain default routing to
   the installed `start-task` skill when merging project instructions. After
   adoption is committed, reuse an existing project coordinator if one is already
   open and have it read the merged instructions. Otherwise, for a ready-to-use Orca
   handoff check that the installed `start --help` lists `--wait-for-task`
   and run `python3 .agents/workflow.py start --wait-for-task` once from the clean
   checkout containing the adoption commit. For 0.2.0, use the main checkout
   after it includes that commit. Give the user the workspace and session from the
   launch receipt. If the installed runtime predates this option, use `start "Your task"` when the
   user supplies their task. If setup ends before the commit or launch, report
   the step still needed.

The [setup skill](skills/setup-orca-workflow/SKILL.md) contains the maintained
installation/adoption procedure, its helpers and platform limits. This entry point
exists so an agent can begin before the skill or Orca is installed.
