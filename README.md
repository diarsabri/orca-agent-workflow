# Orca Agent Workflow

Orca Agent Workflow helps you take a feature idea or bug report from “here’s what I want” to a tested change you can review. You work with one coding assistant throughout. It helps you define what success looks like, gives another agent a specific job, and brings the result back to you.

This is useful when a change touches more than one part of a project or when a small misunderstanding could produce the wrong feature. You can catch a misunderstanding while the plan is still a few sentences long. Later, a reviewer who didn’t write the code checks whether the result does what you agreed.

## How a task works

Suppose you ask, **“Show a weekly total in my habit tracker.”**

1. **Agree on what ‘weekly total’ means.** Your assistant might ask, “If I complete the same habit on three days, should that count as one or three?” You settle on three completions, a Monday start, and zero for an empty week. The assistant writes down those decisions, the files that may change, and how it will test the result. You approve that plan.
2. **Build it in a separate workspace.** Orca gives the task its own working copy of your project. The coding agent can edit only the files approved for this job. If it discovers it also needs to change how habits are stored, it has to ask before expanding the work.
3. **Test it and get a second reading.** Your assistant runs the project’s checks. A fresh reviewer reads the plan and the actual code changes. For example, the tests might pass for an ordinary week, but the reviewer might notice there’s no check for a completion just after midnight on Monday. The coordinator can send it back for a fix and have the revised change checked again.
4. **Decide whether it’s ready.** You get the proposed change, the checks that ran, the reviewer’s findings, and any unresolved questions. On GitHub the change can come to you as a *pull request*, where you can inspect it, request an adjustment, or accept it into the main project.

## What Orca does and what the kit adds

[Orca](https://github.com/stablyai/orca) is the desktop app that manages workspaces and agent sessions. This kit adds the project instructions and tools that connect those sessions. They carry the written plan from one agent to the next, limit which files the coding agent can edit, and record which version was tested and reviewed. If the code changes after review, that earlier review no longer covers it.

You can still ask a quick question or request a small edit in your usual session. The full sequence is for work that benefits from a plan and an independent check.

## Try it in your project

Open your project in **Claude Code, Codex, or OpenCode** and paste this message:

```text
Set up https://github.com/diarsabri/orca-agent-workflow in this project.
Follow INSTALL.md, install Orca if needed, preserve my existing work,
and show me what you verified.
```

Your assistant can help install Orca during setup. For the full workflow, you’ll need a Claude Code account for the agent that edits files. Claude Code or Codex can coordinate the task.

[Walk through your first task](docs/getting-started.md) · [Browse the documentation](docs/README.md)

<details>
<summary>Prefer the command line?</summary>

From your project folder, preview the setup with:

```sh
uvx orca-agent-workflow@0.2.0 init
```

Review the proposed files before adding `--apply`. The [setup reference](docs/setup-reference.md#manual-setup-or-automation) covers manual installation and project checks.

</details>

Independent project for use with [Orca](https://github.com/stablyai/orca). [MIT license](LICENSE).
