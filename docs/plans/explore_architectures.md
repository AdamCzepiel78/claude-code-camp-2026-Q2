# Explore Agent Architecture
## 1. An agent file with referenced files eq. AGENT.md, @~/docs/*.MD

**Model:** Haiku 5.5

### Technical Observations

- During the initial run, the agent did not directly connect to the MUD. Instead, it created a temporary Python script (`mud_play.py`) inside the `/tmp` directory and requested execution permissions.
- The initial connection timed out, causing the agent to repeatedly modify its generated script and retry the connection with different command parameters.
- When the provided dummy credentials failed, the agent went off-task and started exploring the Docker container and repository to locate valid credentials instead of continuing with gameplay.
- After the correct credentials were provided manually, the agent continued refining its Python script before finally connecting to the MUD.
- Rather than relying solely on interaction with the game, the agent requested access to the `lib/world` directory and used the world data to determine the correct path to the bakery.
- The agent eventually reached the bakery and successfully listed the available menu items.
- The workflow involved multiple iterations of script generation, permission requests, retries, and repository exploration, resulting in approximately **27,000 tokens** being consumed for a relatively simple navigation task.
- Frequent approval requests for script modifications and filesystem permissions interrupted the workflow and significantly reduced the overall user experience.

### Technical Conclusions

The current coding harness appears to treat interaction with the MUD as a programming problem instead of a gameplay problem. Rather than connecting and issuing commands directly, it first attempts to generate tooling, debug connection logic, and inspect the repository.

For deterministic workflows such as connecting to the MUD, authenticating, and executing common commands, it would be more efficient to provide a dedicated SDK or interface instead of relying on the model to generate scripts dynamically. This would reduce unnecessary iterations, token consumption, and permission requests.

Providing a well-defined MUD SDK or an MCP server exposing high-level operations (such as **connect**, **login**, **execute command**, and **read output**) would allow the language model to focus on reasoning about the game instead of implementing infrastructure on every run.

The experiment also showed that repository exploration became part of the agent's reasoning process. While this ultimately helped it locate the bakery, it is questionable whether reading world files is desirable if the goal is to evaluate gameplay capabilities rather than source-code analysis.

Overall, while the task was completed successfully, the execution was considerably more expensive than expected. Approximately **27,000 tokens** were consumed for finding a single location and reading its menu, indicating significant room for optimization in the agent architecture. A more specialized interface between the agent and the MUD would likely produce faster, cheaper, and more predictable behavior.

> using conding harnesses for coding, and for specialized agents make your own loop.

## 2. Agent Skills driven by main agent eq. ~/.skills

Agentic AI skills are a way to implement special functionality for an AI. They let the AI use tools, follow steps, and complete specific tasks to reach a goal.

**Models:** Haiku 4.5, Opus 4.8, Sonnet 4.6

### Technical Observations

- Created the `02_agent_skills` directory and launched Claude Code with **Haiku 4.5** at **Effort: High**. The Coding Harness was asked to create a MUD game skill that connects to `localhost:4000` with credentials `dummy / helloworld` and is capable of playing CircleMUD.
- Haiku 4.5 prompted for permissions repeatedly — roughly **10 confirmation dialogs** for script creation and directory permission changes.
- The skill structure was only partially correct: `.claude/skills/mud/SKILL.md` was created as expected, but the Python scripts ended up in the parent folder under `02_agent_skills` instead of the skill's script directory.
- Switched to **Opus 4.8** for cleanup with the prompt: *"Update the /mud skill by optimizing its definition, updating the scripts, and moving them into the correct script directory. Read the Claude Skill documentation first if you're unsure how it works."*
- Opus cleaned up the directory structure quickly — it moved the scripts into the correct directory and updated the `SKILL.md` without unnecessary iterations.
- Testing the skill with **Haiku 4.5** failed again, even after `/reload-skills` and explicitly invoking the `/mud` skill command. The Coding Harness could not work with the skill properly.
- Switched to **Sonnet 4.6**. After a few iterations and adjustments to the skill and the Python scripts, the Coding Harness successfully located the bakery and listed the available items.
- Since the skill quality was still uncertain, the skill was rewritten and extended with two example prompts. The Coding Harness under Sonnet 4.6 solved both prompted tasks successfully.
- Switched back to **Haiku 4.5** for a final test. With the efficiently set up skill in place, the prompted tasks were executed easily while burning fewer tokens — including a complete combat run in the newbie zone (fighting a drunk at the Grunting Boar Inn: 6 combat rounds, victory with zero damage taken, +149 exp gained).

### Technical Conclusions

Choosing small models without a well-defined skill burned a lot of tokens on not very effective tasks. The Coding Harness with higher models was better and more effective at both creating and executing the skill.

The key finding: a skill needs to be tested and optimized with a higher model first — once the skill definition is solid, lower models can work with it reliably for quick tasks. Skill quality determines model performance more than model size.

> Build and optimize skills with strong models, then run them with small models for cost-efficient execution.

