## This is technical exploration.

Did setup Andrews 01_plain_agent and let claude work with haiku 5.5 model / high effort run.
The Promt in Claude Code was: "Play the game and find the bakery and tell me whats on the menu".
the first thing i figured out is that the agent created script in the /tmp folder , created a mud_play.py Python file and requested execute permissions.
the connection also timeouted and the agent started to update its mud_play.py script. It also passed multiple mud command parameters to the script.
Another issue occured when it continued with its calculation. The dummy credentials were rejected - so claude invested some time explore the docker container and the repo to get the credentials.
after added the credentials into a promt in the session and the agent continued to upgrade its script.
Then the agent started the game with its Python script and started to explore the world. It then suddenly stopped and ask for mermissions into lib/world folder to get the world data.
Finally the agent get the right path with help of the world data and displayed the right direction to the bakery. After that he showed the items to sell from the bakery.

After i get the information i was a little bit confused, the haiku 5.5 agent used a lot of tokens and iterated multiple times through its calculation. And it was exhausting being requested for approval of changing script, giving permissions in Haiku 5.5.
I expected at the beginning that the agent directly connects to the game and plays the game, but it generated script, explored the world files and then played the game. 
For this task 27k token burned. I am not sure whether there is an easier way to get to the goal - hope we find find one.


