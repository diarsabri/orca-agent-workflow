# Orca Agent Workflow

Orca Agent Workflow helps you change software with a team of AI coding assistants. One plans the work with you, another writes the code, and a fresh reviewer checks it. You approve the plan and decide what goes into your project.

## How a task works

Suppose you ask, **“Show a weekly total in my habit tracker.”**

1. **Agree on the plan.** Your assistant acts as the coordinator. It might ask when your week starts and whether to count each habit once or every time you complete it. You approve what the total should mean and which files the agent may change.
2. **Make the change.** Orca gives the task its own workspace. A separate coding agent edits the approved files there.
3. **Check the result.** The coordinator runs the project’s checks. A fresh reviewer examines the whole change. For example, does a habit completed on Sunday night count toward the correct week?
4. **Decide whether to use it.** You see the proposed changes, which checks passed, and any open concerns. You decide whether to add the weekly total to your app.

## Try it in your project

Open your project in **Claude Code, Codex, or OpenCode** and paste this message:

```text
Set up https://github.com/diarsabri/orca-agent-workflow in this project.
Follow INSTALL.md, install Orca if needed, preserve my existing work,
and show me what you verified.
```

Orca is the desktop app that manages the agents’ workspaces. You can start setup before installing it. For the full workflow, you’ll need a Claude Code account for the agent that edits files. Claude Code or Codex can coordinate the task.

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
