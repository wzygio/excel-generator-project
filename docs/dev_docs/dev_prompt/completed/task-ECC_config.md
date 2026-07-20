You are helping me make ECC hooks work reliably with Codex.

Goal:
I want Codex hooks to run automatically during Codex development sessions. I have or plan to install ECC, but I do not want to assume ECC has already configured Codex-native hooks correctly. Please inspect the current repository and Codex configuration, then create or repair a minimal, safe, Codex-native hooks setup.

Important principles:

1. Do not overwrite existing ECC, Codex, MCP, skills, or AGENTS.md configuration blindly.
2. Prefer project-level hooks under `.codex/` before modifying global `~/.codex/`.
3. Preserve all existing ECC configuration.
4. Do not copy Claude Code hooks directly into Codex hooks unless they are translated to Codex-native hook format.
5. Make the smallest safe change.
6. Before editing files, report what you found and what you plan to change.
7. After editing files, provide verification steps and expected results.

Please perform the following steps.

Step 1: Inspect current Codex and ECC configuration

Check for these files and directories:

* `AGENTS.md`
* `.codex/`
* `.codex/config.toml`
* `.codex/hooks.json`
* `.codex/hooks/`
* `.codex/skills/`
* `.agents/skills/`
* `~/.codex/config.toml`
* `~/.codex/hooks.json`
* `~/.codex/hooks/`
* `~/.codex/skills/`

Also inspect any ECC-related files that appear relevant, such as:

* ECC synced skills
* ECC MCP config
* ECC AGENTS.md additions
* ECC hook scripts
* ECC security or memory scripts

Report whether ECC appears to be installed or partially synced.

Step 2: Check whether Codex hooks are enabled

Inspect Codex config files and determine whether hooks are disabled.

Look for:

```toml
[features]
hooks = false
```

If hooks are disabled, recommend changing it to:

```toml
[features]
hooks = true
```

Do not change it until you have reported the finding.

If there is no explicit setting, note that hooks may be enabled by default, but we will still verify with a smoke test.

Step 3: Inspect existing hook sources

Check whether hooks are currently defined in any of these places:

* `.codex/hooks.json`
* `.codex/config.toml`
* `~/.codex/hooks.json`
* `~/.codex/config.toml`

For each hook source, list:

* hook event name
* matcher
* command
* whether it appears ECC-related
* whether it appears duplicated globally and locally
* whether it uses Unix-only commands
* whether it has a Windows-compatible command

Important:
Codex may load multiple hook sources. Do not create duplicate hooks that run the same logic twice.

Step 4: Build a minimal Codex-native smoke test

Before migrating ECC hooks, create a minimal project-level hook smoke test under `.codex/`.

Preferred files:

* `.codex/hooks.json`
* `.codex/hooks/session_start_test.py`
* `.codex/hooks/pre_tool_use_test.py`
* `.codex/hooks/post_tool_use_test.py`
* `.codex/hooks/stop_test.py`
* `.codex/hooks-test.log`

The smoke test should verify these events:

* `SessionStart`
* `PreToolUse`
* `PostToolUse`
* `Stop`

Each test script should append a line to `.codex/hooks-test.log` including:

* timestamp
* hook event name
* current working directory
* whether stdin was received
* a short success marker

Use Python for cross-platform compatibility.

For each command hook, include a Windows-compatible command when appropriate.

Example intent:

* On Unix/macOS/Linux: `python3 .codex/hooks/session_start_test.py`
* On Windows: `py .codex\\hooks\\session_start_test.py` or `python .codex\\hooks\\session_start_test.py`, depending on what is available.

Please detect the local environment and choose the safest command. If uncertain, include both `command` and `commandWindows`.

Step 5: Use Codex-native hook format

Use Codex-native `hooks.json` format, not Claude Code hook format.

Create or merge hook entries for:

* `SessionStart`
* `PreToolUse`
* `PostToolUse`
* `Stop`

Do not overwrite existing hooks. Merge safely.

If `.codex/hooks.json` already exists:

* parse it
* preserve existing entries
* add only missing smoke-test entries
* avoid duplicate commands
* keep the JSON valid and formatted

If no `.codex/hooks.json` exists:

* create one with only the minimal smoke-test hooks

Step 6: Do not migrate ECC hooks yet

At this stage, do not migrate full ECC hooks.

Only create the smoke-test hooks first.

Reason:
We need to verify Codex hook discovery, trust, event matching, command execution, and Windows compatibility before attaching ECC security, memory, planning, or verification logic.

Step 7: Add a small local README if useful

If helpful, create:

* `.codex/hooks/README.md`

It should explain:

* these are Codex-native hooks
* they are currently smoke-test hooks
* they are not copied directly from Claude Code
* they should be trusted via `/hooks` in Codex
* once verified, ECC logic can be migrated gradually

Keep this README concise.

Step 8: Report required manual trust step

After creating or updating hooks, explain that I need to open Codex and run:

```text
/hooks
```

Then I should:

1. inspect detected hook sources
2. review the new project-level hooks
3. trust or enable them
4. start a new session or trigger tool usage
5. check `.codex/hooks-test.log`

Step 9: Provide verification procedure

Provide exact commands or actions to verify:

1. Start a new Codex session in this repository.
2. Run `/hooks` and trust the hooks if prompted.
3. Ask Codex to run a harmless Bash command, such as:

   * `pwd`
   * `echo hook-test`
4. Stop or complete the task.
5. Inspect `.codex/hooks-test.log`.

Expected result:
The log should contain entries for:

* `SessionStart`
* `PreToolUse`
* `PostToolUse`
* `Stop`

If any event is missing, diagnose whether the issue is:

* hook source not discovered
* hook not trusted
* matcher not matching
* command path issue
* Python command issue
* Windows command issue
* hooks disabled in config
* Codex version or runtime issue

Step 10: Prepare for ECC hook migration after smoke test

After smoke tests pass, propose a phased migration plan for ECC-related hook logic.

Recommended migration order:

1. `SessionStart`

   * load project state
   * load planning files
   * load relevant memory summary

2. `UserPromptSubmit`

   * detect secrets in user prompt
   * remind Codex of ECC workflow if needed

3. `PreToolUse`

   * block dangerous shell commands
   * warn before destructive git operations
   * prevent accidental secret exposure

4. `PostToolUse`

   * log test results
   * log modified files
   * remind to update progress files

5. `Stop`

   * verify tests were considered
   * verify planning files were updated for complex tasks
   * summarize remaining work

6. `PreCompact` / `PostCompact`

   * later enhancement only
   * save state before context compression

Do not implement these full ECC hook migrations until the smoke-test hooks are verified.

Step 11: Final report

After making minimal changes, provide a final report with:

1. Files inspected
2. Files changed
3. Existing ECC config preserved
4. Existing hooks preserved
5. New smoke-test hooks added
6. Whether hooks are explicitly enabled
7. Whether global/project hook duplication was found
8. Windows compatibility notes
9. Manual `/hooks` trust steps
10. Verification instructions
11. Proposed next step after smoke test passes

Final mental model:

* ECC provides skills, rules, MCP config, security workflow, and broader agent harness assets.
* Codex hooks must be configured using Codex-native hook files and trusted by Codex.
* Do not assume ECC automatically installed Codex hooks.
* First verify hooks with a minimal smoke test.
* Only after smoke-test success should ECC hook logic be migrated gradually.
