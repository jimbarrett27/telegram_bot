# D&D Bot Improvement List

## Done
- [x] **#9 Agent architecture** — Refactored to ReAct agent with LangGraph. DM agent with tools (roll_dice, get_party_status, apply_damage, get_recent_history). Jinja2 templates removed.
- [x] **#4 Rules enforcement & inventory tracking** — Character attributes (STR, DEX, etc.) in DB. Inventory items table. Spell slots table. Rules lawyer sub-agent validates physical actions. Spell checker sub-agent validates spell casting. Bundled SRD JSON data (equipment, spells, mechanics, combat). Pre-rolled character templates per class (#5). Enhanced /dnd_sheet with attributes, inventory, spell slots (#6).
- [x] **#5 Pre-rolled characters with detailed stats** — Done as part of #4.
- [x] **#6 Character sheet & inventory command** — Done as part of #4.

## To Do
- [x] **#1 Fix command auto-send behaviour** — `/dnd_action` (no args) now prompts player to type action as plain text. Done as part of #2.
- [x] **#2 Conversational action resolution (DM dialogue)** — ConversationHandler with `request_clarification` tool. DM can ask questions before resolving. Player responds via plain text. Max 25 exchanges. `/dnd_cancel` to abort.
- [ ] **#3 Dice rolling / randomness system** — `roll_dice` tool exists, DM system prompt instructs use. May need further enforcement/testing.
- [ ] **#7 Game grid / spatial tracking** — Background grid/map for tracking positions of characters, monsters, terrain, distances.
- [x] **#8 PDF campaign loading** — pymupdf PDF parser extracts text and splits into sections by heading detection. Sections stored in campaign_sections DB table. DM agent has lookup_campaign and list_campaign_sections tools. `/dnd_start [adventure_name]` loads a PDF adventure.
