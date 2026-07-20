
# Preweek Technical Documentation

## Technical Goal

Before diving into the actual bootcamp weeks, the goal was to just try out a couple of agent architectures and see how they behave when you ask them to play the MUD (tbaMUD / CircleMUD) autonomously. Two setups so far: a plain agent that only gets a CLAUDE.md with referenced files (world.md, player.md), and an agent-skills setup where the gameplay logic lives in a `.claude/skills` skill instead of just a prompt file. Task in both cases was basically the same: play the game, find the bakery, tell me what's on the menu.

## Technical Uncertainty

Wasn't sure whether a general coding harness (Claude Code) is even the right tool to drive something like a MUD session, or if it would just try to "solve" the game like a programming problem. Also unclear whether cheap/small models like Haiku can carry a gameplay loop on their own, or if they need a lot of hand-holding (and tokens) to get anywhere. And for the skills approach specifically - no idea yet whether a skill written by one model would even work when a different model tries to run it.

## Technical Hypotheses

Expected the agent to just connect to `localhost:4000`, log in, and start issuing MUD commands more or less directly - basically treating it like a scripted gameplay session rather than a coding task. Figured token cost would be small since "walk to the bakery and read the menu" isn't a hard problem.

## Technical Observerations

**Plain agent (CLAUDE.md only), Haiku 5.5, high effort:**
Instead of connecting directly, the agent wrote itself a `mud_play.py` in `/tmp` and asked for execute permission first. The connection timed out a couple times, so it kept patching the script and retrying with different params. When the dummy credentials it was given didn't work, it went off-script entirely and started poking around the Docker container and the repo to dig up working credentials instead of just asking. Once it had those, it went back to tweaking the Python script some more before it actually connected. On top of that it asked for access to `lib/world` and used the raw world data to figure out the path to the bakery rather than just navigating by feel. It did get there in the end and listed the menu - but the whole thing burned about **27k tokens** for what should've been a five-minute walk, and there were constant approval prompts for scripts/permissions along the way.

**Agent skills, Haiku 4.5 / Opus 4.8 / Sonnet 4.6:**
Asked Haiku 4.5 (high effort) to build a `/mud` skill for the same connect-and-play task. It prompted for permissions ~10 times just to create scripts and set up directories, and even then it put the skill's Python scripts in the wrong folder (parent dir instead of the skill's own script directory) - only `SKILL.md` ended up where it should. Switched to Opus 4.8 to clean it up, which it did quickly and without drama. Went back to Haiku 4.5 to actually test the skill - failed again, even after `/reload-skills` and calling `/mud` explicitly, Haiku just couldn't drive it properly. Sonnet 4.6 finally got it working, found the bakery, listed the items. Since the skill quality still felt shaky, rewrote it with two example prompts and had Sonnet validate both - worked fine. Went back to Haiku 4.5 one more time with the now-solid skill in place, and this time it flew through the tasks with way less token burn, including a full newbie-zone fight (drunk at the Grunting Boar Inn, 6 rounds, won without taking damage, +149 exp).

## Technical Conclusions

Both runs point the same direction: the coding harness treats "play the MUD" as a programming problem by default - generate a script, debug the connection, inspect the repo - instead of just doing the gameplay. For something this deterministic (connect, login, send command, read output) it'd make a lot more sense to hand the model a proper interface, like an SDK or an MCP server with high-level actions, instead of letting it improvise scripts every single run. That should cut down on iterations, tokens, and the constant permission back-and-forth.

For the skills side specifically: model size mattered less than skill quality. A shaky skill made even Haiku unusable, while a properly tested one let Haiku run cheap and reliable afterward. So the move seems to be: build/debug the skill with a strong model first, and only hand it to a small model once it's solid.

Also questionable whether letting the agent read raw world files to solve navigation is even desirable if the point is to evaluate gameplay ability rather than let it cheat via source access - something to keep an eye on in later architectures (subagent SDK variants already in progress under `03a/03b/03c_subagent_sdk`).

## Key Takeaway

Coding harnesses default to writing code for everything, even a simple gameplay loop - so if you want small models to run cheap and reliably, build a proper interface (skill or SDK) with a strong model first, then hand it down.
