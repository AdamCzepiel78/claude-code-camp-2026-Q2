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


