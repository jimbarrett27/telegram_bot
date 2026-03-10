from typing import Optional


class Narrator:
    async def narrate_scene(self, round_number: int, previous_resolution: Optional[str]) -> str:
        """Generate the scene-setting narrative for a new round."""
        if round_number == 1:
            return "The adventure begins... The narrator sets the scene."
        return f"Round {round_number}. The story continues..."

    async def resolve_round(self, narrative: str, actions: list[tuple[str, str]]) -> str:
        """Resolve the round given the narrative and player actions.

        actions is a list of (player_name, action_text) tuples.
        """
        summary = "\n".join(f"  {name}: {action}" for name, action in actions)
        return f"The narrator considers everyone's actions:\n{summary}\n\nThe round resolves..."
