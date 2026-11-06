# Refreshing Crown (watchdog step; ElevenLabs is not reachable from this machine, so push through the ElevenLabs connector)
Crown's text is stored directly (no dynamic variables): the ElevenLabs talk-to page and the dashboard do not supply them, and a missing variable stops Crown from starting.
1. python3 /home/user/cbf-gold-desk/scan/crown_brief.py  -> writes /home/user/gold-desk/crown/crown_vars.json (desk_brief, prompt)
2. mcp__ElevenLabs__agents_update_prompt_settings, agent_id agent_3401m5j08eqgf6ascsd9ttbf1mgw, prompt = crown_vars "prompt" exactly. Change nothing else.
3. mcp__ElevenLabs__agents_update_agent_behavior, same agent, first_message = crown_vars "desk_brief" exactly,
   dynamic_variables {"dynamic_variable_placeholders": {}}. Change nothing else.
4. If ElevenLabs fails, say so in the reply and carry on.

Dashboard refresh (same run, after Crown; trader asked on 6 Nov for the dashboard to show the live desk):
5. python3 /home/user/cbf-gold-desk/scan/desk_json.py, then cp /home/user/gold-desk/crown/desk.json /tmp/claude-0/-home-user-cbf-gold-desk/d2f16d0e-dc9e-567e-bf61-47dec9735a7a/scratchpad/dash/desk.json
6. Artifact publish with url https://claude.ai/artifact/3GSRaPMgJGLq3Vg7MJ733x, file_path that scratchpad desk.json, asset: true. Note the returned /_blob/<id> url.
7. ArtifactData get datasets/desk on that url, then update datasets/desk (if_version = its version) with source.url = the new /_blob url (keep kind file, name desk.json, format json), updated {at: now UTC ISO, by: "Claude (gold desk)"}, edit {via: "claude", at: now}.
8. Delete the previous desk.json asset (Artifact delete with url and path = the old blob id) only if it was uploaded by this desk.
