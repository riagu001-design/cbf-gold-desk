# Refreshing Crown (watchdog step; ElevenLabs is not reachable from this machine, so push through the ElevenLabs connector)
Crown's text is stored directly (no dynamic variables): the ElevenLabs talk-to page and the dashboard do not supply them, and a missing variable stops Crown from starting.
1. python3 /home/user/cbf-gold-desk/scan/crown_brief.py  -> writes /home/user/gold-desk/crown/crown_vars.json (desk_brief, prompt)
2. mcp__ElevenLabs__agents_update_prompt_settings, agent_id agent_3401m5j08eqgf6ascsd9ttbf1mgw, prompt = crown_vars "prompt" exactly. Change nothing else.
3. mcp__ElevenLabs__agents_update_agent_behavior, same agent, first_message = crown_vars "desk_brief" exactly,
   dynamic_variables {"dynamic_variable_placeholders": {}}. Change nothing else.
4. If ElevenLabs fails, say so in the reply and carry on.
