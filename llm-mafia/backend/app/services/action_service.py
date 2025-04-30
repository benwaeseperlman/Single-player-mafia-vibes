from uuid import UUID
from typing import Type, Union, Dict, Optional

from app.models.game import GameState, GamePhase
from app.models.player import Player, Role, PlayerStatus
from app.models.actions import (
    ActionType,
    BaseAction,
    MafiaKillAction,
    DetectiveInvestigateAction,
    DoctorProtectAction,
)


class ActionValidationError(Exception):
    """Custom exception for action validation errors."""
    pass


class ActionService:
    """Handles recording and potentially resolving player actions."""

    def __init__(self) -> None:
        # Map role to the action type they perform at night
        self.role_to_night_action: Dict[Role, ActionType] = {
            Role.MAFIA: ActionType.MAFIA_KILL,
            Role.DETECTIVE: ActionType.DETECTIVE_INVESTIGATE,
            Role.DOCTOR: ActionType.DOCTOR_PROTECT,
        }
        # Map action type to its corresponding Pydantic model
        self.action_type_to_model: Dict[ActionType, Type[BaseAction]] = {
            ActionType.MAFIA_KILL: MafiaKillAction,
            ActionType.DETECTIVE_INVESTIGATE: DetectiveInvestigateAction,
            ActionType.DOCTOR_PROTECT: DoctorProtectAction,
        }

    def _validate_night_action(
        self,
        game_state: GameState,
        player: Player,
        target: Player,
        action_type: ActionType,
    ) -> None:
        """Performs validation checks before recording a night action."""
        if game_state.phase != GamePhase.NIGHT:
            raise ActionValidationError("Night actions can only be performed during the Night phase.")

        if player.status != PlayerStatus.ALIVE:
            raise ActionValidationError("Player must be alive to perform an action.")
        
        if target.status != PlayerStatus.ALIVE:
            raise ActionValidationError("Target player must be alive.")
        
        if player.id == target.id and action_type == ActionType.MAFIA_KILL:
             raise ActionValidationError("Mafia cannot target themselves for a kill.")

        # Check if the player's role allows this action type
        expected_action = self.role_to_night_action.get(player.role)
        if not expected_action or expected_action != action_type:
            raise ActionValidationError(f"Player role '{player.role.value}' cannot perform action '{action_type.value}'.")
            
        # Check if the player has already acted this night
        if player.id in game_state.night_actions:
            raise ActionValidationError("Player has already performed their action this night.")
            
        # TODO: Add Doctor specific rules (no self-protect, no repeat target) if required by game design

    def _get_player_by_id(self, game_state: GameState, player_id: UUID) -> Optional[Player]:
        """Helper to find a player in the game state by ID."""
        for p in game_state.players:
            if p.id == player_id:
                return p
        return None

    def record_night_action(
        self,
        game_state: GameState,
        player_id: UUID,
        target_id: UUID,
        action_type: ActionType,
    ) -> None:
        """
        Records a night action for a player targeting another player.

        Args:
            game_state: The current game state.
            player_id: The ID of the player performing the action.
            target_id: The ID of the player being targeted.
            action_type: The type of night action being performed.

        Raises:
            ActionValidationError: If the action is invalid (wrong phase, dead player, role mismatch, etc.).
            ValueError: If player_id or target_id is not found in the game state.
        """
        player = self._get_player_by_id(game_state, player_id)
        target = self._get_player_by_id(game_state, target_id)

        if not player:
            raise ValueError(f"Player with ID {player_id} not found in game state.")
        if not target:
             raise ValueError(f"Target player with ID {target_id} not found in game state.")

        self._validate_night_action(game_state, player, target, action_type)

        action_model_class = self.action_type_to_model.get(action_type)
        if not action_model_class:
            # This should not happen if action_type is validated correctly
            raise ValueError(f"Unsupported action type: {action_type.value}")

        action = action_model_class(player_id=player_id, target_id=target_id)
        
        # Special case for Mafia Kill - requires consensus or specific handling if multiple Mafia
        # For now, assume one Mafia or the first action is the one taken.
        # TODO: Implement logic for multiple Mafia members coordinating a kill.
        if action_type == ActionType.MAFIA_KILL:
            # Store under a generic key for Mafia kill or handle multiple Mafia votes later
            # For simplicity now, we'll overwrite previous mafia kill actions if multiple exist
            # A better approach might be needed for actual multi-mafia voting.
             mafia_action_key = ActionType.MAFIA_KILL # Use the type itself as a placeholder key for the kill decision
             game_state.night_actions[mafia_action_key] = action # Store the action itself
        else:
             game_state.night_actions[player.id] = action

        game_state.updated_at = action.timestamp # Update game state timestamp
        print(f"Recorded action: {action_type.value} by {player_id} on {target_id}") # Basic logging


# Placeholder for action resolution logic, likely called by phase_logic.py
# def resolve_night_actions(game_state: GameState) -> GameState:
#     """Processes all recorded night actions and updates the game state."""
#     # ... implementation needed ...
#     # - Find Mafia target
#     # - Check if Doctor saved target
#     # - Process Detective investigation
#     # - Update player statuses (killed, etc.)
#     # - Set investigation results
#     # - Clear night_actions for next night
#     pass 