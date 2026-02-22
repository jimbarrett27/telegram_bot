# D&D Bot Improvement List

## Done
- [x] **#9 Agent architecture** — Refactored to ReAct agent with LangGraph. DM agent with tools (roll_dice, get_party_status, apply_damage, get_recent_history). Jinja2 templates removed.
- [x] **#4 Rules enforcement & inventory tracking** — Character attributes (STR, DEX, etc.) in DB. Inventory items table. Spell slots table. Rules lawyer sub-agent validates physical actions. Spell checker sub-agent validates spell casting. Bundled SRD JSON data (equipment, spells, mechanics, combat). Pre-rolled character templates per class (#5). Enhanced /dnd_sheet with attributes, inventory, spell slots (#6).
- [x] **#5 Pre-rolled characters with detailed stats** — Done as part of #4.
- [x] **#6 Character sheet & inventory command** — Done as part of #4.

## To Do
- [ ] **#1 Fix command auto-send behaviour** — `/dnd_action` sends immediately on tap without letting you type the action description. Need to rework command input flow.
- [ ] **#2 Conversational action resolution (DM dialogue)** — Allow back-and-forth with the DM to clarify actions before resolving (e.g. "which goblin?", "you don't have a spear"). Related to #1.
- [ ] **#3 Dice rolling / randomness system** — `roll_dice` tool exists, DM system prompt instructs use. May need further enforcement/testing.
- [ ] **#7 Game grid / spatial tracking** — Background grid/map for tracking positions of characters, monsters, terrain, distances.
- [ ] **#8 PDF campaign loading** — Load published adventures from PDF (e.g. `adventures/Wiebe_TheHangover.pdf`). Parse, chunk, feed to DM agent. Work out approach together.
