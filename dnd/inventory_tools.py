"""
Inventory management tools for the DM agent.

These are direct tools the DM uses to view and modify player inventories
during gameplay (e.g., picking up loot, consuming potions, breaking weapons).
"""

import logging

from langchain_core.tools import tool

from dnd.database import (
    get_game_by_id,
    get_player_inventory,
    add_inventory_item,
    remove_inventory_item_by_name,
    update_inventory_item_equipped,
)

logger = logging.getLogger(__name__)


class InventoryTools:
    """Tools for managing player inventories, bound to a specific game."""

    def __init__(self, game_id: int):
        self.game_id = game_id

    def _find_player(self, player_name: str):
        """Find a player by name (case-insensitive). Returns (player, error_msg)."""
        game = get_game_by_id(self.game_id)
        if game is None:
            return None, "Error: game not found."
        for p in game.players:
            if p.character_name.lower() == player_name.lower():
                return p, None
        names = [p.character_name for p in game.players]
        return None, f"No player named '{player_name}'. Available: {', '.join(names)}"

    def as_tools(self):
        """Return LangChain tools bound to this game."""
        ctx = self

        @tool
        def check_inventory(player_name: str) -> str:
            """Check a player's current inventory.

            Returns a list of all items the player is carrying, including
            quantities and whether items are equipped.

            Args:
                player_name: The character name to check
            """
            logger.info("check_inventory called for player=%r", player_name)
            player, err = ctx._find_player(player_name)
            if err:
                return err

            items = get_player_inventory(player.id)
            if not items:
                return f"{player.character_name} has no items."

            lines = [f"Inventory for {player.character_name}:"]
            for item in items:
                equipped = " [EQUIPPED]" if item.equipped else ""
                qty = f" x{item.quantity}" if item.quantity > 1 else ""
                lines.append(f"  - {item.item_name}{qty} ({item.item_type}){equipped}")
            return "\n".join(lines)

        @tool
        def add_item(player_name: str, item_name: str, quantity: int = 1, item_type: str = "gear") -> str:
            """Give an item to a player (e.g., loot, quest reward, purchased item).

            Args:
                player_name: The character name to give the item to
                item_name: Name of the item
                quantity: How many to add (default 1)
                item_type: Type of item — 'weapon', 'armor', 'potion', 'gear', 'spell_component'
            """
            logger.info("add_item called: player=%r item=%r qty=%d", player_name, item_name, quantity)
            player, err = ctx._find_player(player_name)
            if err:
                return err

            add_inventory_item(
                player_id=player.id,
                game_id=ctx.game_id,
                item_name=item_name,
                item_type=item_type,
                quantity=quantity,
            )
            return f"Added {quantity}x {item_name} to {player.character_name}'s inventory."

        @tool
        def remove_item(player_name: str, item_name: str, quantity: int = 1) -> str:
            """Remove an item from a player's inventory (e.g., consumed potion, thrown weapon, broken item).

            Args:
                player_name: The character name
                item_name: Name of the item to remove
                quantity: How many to remove (default 1)
            """
            logger.info("remove_item called: player=%r item=%r qty=%d", player_name, item_name, quantity)
            player, err = ctx._find_player(player_name)
            if err:
                return err

            success = remove_inventory_item_by_name(player.id, item_name, quantity)
            if success:
                return f"Removed {quantity}x {item_name} from {player.character_name}'s inventory."
            return f"{player.character_name} doesn't have '{item_name}' in their inventory."

        @tool
        def equip_item(player_name: str, item_name: str) -> str:
            """Equip an item from a player's inventory.

            Args:
                player_name: The character name
                item_name: Name of the item to equip
            """
            logger.info("equip_item called: player=%r item=%r", player_name, item_name)
            player, err = ctx._find_player(player_name)
            if err:
                return err

            items = get_player_inventory(player.id)
            for item in items:
                if item.item_name.lower() == item_name.lower():
                    update_inventory_item_equipped(item.id, True)
                    return f"{player.character_name} equipped {item.item_name}."
            return f"{player.character_name} doesn't have '{item_name}' to equip."

        @tool
        def unequip_item(player_name: str, item_name: str) -> str:
            """Unequip an item (put it back in the pack).

            Args:
                player_name: The character name
                item_name: Name of the item to unequip
            """
            logger.info("unequip_item called: player=%r item=%r", player_name, item_name)
            player, err = ctx._find_player(player_name)
            if err:
                return err

            items = get_player_inventory(player.id)
            for item in items:
                if item.item_name.lower() == item_name.lower() and item.equipped:
                    update_inventory_item_equipped(item.id, False)
                    return f"{player.character_name} unequipped {item.item_name}."
            return f"{player.character_name} doesn't have '{item_name}' equipped."

        return [check_inventory, add_item, remove_item, equip_item, unequip_item]
