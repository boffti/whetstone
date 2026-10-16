---
name: whetstone-agent
description: Keep watching Whetstone in the background and do the work the learner asks for in the app (build a module, a review variant, a whole path, a review, a profile refresh) while also pairing live. Use when the learner says "watch Whetstone", "listen to Whetstone", "be my Whetstone agent", or presses Prepare in the app while you are running.
---

# Agent: watch Whetstone and do what the learner asks

In the app, the learner presses **Prepare**, **Prepare review variant** or **Prepare all missing modules**. Whetstone queues a request. You are the one who does the work. Whetstone never starts an agent itself: it waits for you.

## Start

1. Run `bin/whetstone requests` to see work that is already queued.
2. Run `bin/whetstone watch` as a **background** process whose output wakes you. In Claude Code, use the Monitor tool. Without a background monitor, run `bin/whetstone watch --for 120` whenever the learner says "check".
   - While the watch runs, the app shows **Agent connected** in its top bar.
   - The watch first replays queued requests as `requested` events, then streams new events as they happen.
3. Tell the learner in one line: "Watching Whetstone. Press Prepare in the app, or keep practising."

## On a `requested` event

Each event has `id`, `kind`, `target` and `ask`. `ask` is the job in plain words. Handle one request at a time, oldest first.

1. `bin/whetstone request claim <id>`. The app now shows *Your agent is building*.
2. Do the job with the matching skill:

   | `kind` | `target` | Do |
   |---|---|---|
   | `build` | a module id | `whetstone-author`: the module's next question |
   | `variant` | a question key | `whetstone-author`: a variant for spaced review, with `variant_of` set |
   | `fill-path` | a path id | `whetstone-author`: the first question of each unbuilt module in the path |
   | `review` | a question key | `whetstone-review`, then put the main points in the app with `bin/whetstone note` |
   | `profile` | (none) | `whetstone-profile`. It needs the learner's consent, so ask in the chat first. |

3. Finish the request:
   - When it worked: `bin/whetstone request done <id> --result <question key>`. The app turns the button into **Start**. For `fill-path`, pass the first new key.
   - When it can't be done: `bin/whetstone request fail <id> --result "<one line: why, and what would fix it>"`. The app shows the reason.
4. In the chat, give a short line: what you built and what it practises. Never describe the solution.

If several requests arrive while you are building, finish the current one first. Then run `bin/whetstone requests` and continue.

## Other events

Events about the learner's own work, such as `opened`, `paused`, `ran`, `hint`, `solution` and `idle`, are live-pair events. Follow the `whetstone-pair` skill for those, and respect the `pair` mode they carry. In `off` mode, handle requests but stay silent about their work.

## Rules

- Never edit the learner's code, drafts or `my/whetstone.db` directly. Use the CLI.
- Every question still goes through `bin/whetstone question add`, which checks it before filing.
- Never copy anything from `my/` into `content/`, `examples/` or a commit.
- Stop watching when the learner says stop. Requests stay queued until an agent comes back.
