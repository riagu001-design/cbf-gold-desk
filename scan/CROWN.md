# Refreshing Crown (watchdog step; ElevenLabs is not reachable from this machine, so push through the ElevenLabs connector)
1. python3 /home/user/cbf-gold-desk/scan/crown_brief.py  -> writes /home/user/gold-desk/crown/crown_vars.json
2. mcp__ElevenLabs__agents_update_agent_behavior, agent_id agent_3401m5j08eqgf6ascsd9ttbf1mgw, first_message "{{desk_brief}}",
   dynamic_variables {"dynamic_variable_placeholders": {"desk_brief": <crown_vars desk_brief>, "desk_state": <crown_vars desk_state>,
   "live_now": "Not available: Woody opened Crown outside the dashboard. Use the desk snapshot price and say its time."}}
   (all three keys every time: the call replaces the whole set). Change nothing else on the agent.
3. If ElevenLabs fails, say so in the reply and carry on.
