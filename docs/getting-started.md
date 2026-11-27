# Your first task

Start with a small change in a project you already know. Pick something you can recognize when it works, such as adding a weekly total to a habit tracker.

## 1. Set up the workflow once

Open your project in Claude Code, Codex, or OpenCode. Paste this message:

```text
Set up https://github.com/diarsabri/orca-agent-workflow in this project.
Follow INSTALL.md, install Orca if needed, preserve my existing work,
and show me what you verified.
```

Your assistant checks what is installed, prepares the project instructions, and helps configure the checks your project needs. It may ask you to sign in or approve a system permission. Ask it to show you the proposed files, the checks it actually ran, and anything still missing. Review the setup changes and commit them before starting a task.

For the full workflow, Claude Code or Codex can coordinate. Claude Code is required to edit the files, and the standard project checks run in Docker. If setup stops, use the [setup reference](setup-reference.md) or check [which tools are supported](compatibility.md).

If you prefer a terminal, `uvx orca-agent-workflow@0.2.0 init` previews the setup files. Follow the [manual setup steps](setup-reference.md#manual-setup-or-automation) to finish.

## 2. Describe the change

Use the project’s coordinator session in Orca. If setup opened one for you, continue there. In an existing Claude Code or Codex session, ask it to read the updated project instructions first. [Opening or finding a session](setup-reference.md#start-a-task)

> Show a weekly total on the habit tracker’s home screen. Count completed habits from Monday through Sunday and show zero if I haven’t completed any.

The coordinator turns your request into a plan. Read what it proposes to change and how it will check the result. If it proposes changing the calendar screen when you asked for the home screen, correct that now. Once you approve the plan, a separate agent can edit the agreed files.

## 3. Decide whether the work is ready

The coordinator runs the project’s checks and arranges a fresh review. Ask it to show how the change behaves, which checks ran, and what the reviewer found. If a check failed or the review was incomplete, ask what still needs attention.

When you’re satisfied, you decide whether to **merge** the change, which adds it to the main version of your project.

[Documentation index](README.md)
