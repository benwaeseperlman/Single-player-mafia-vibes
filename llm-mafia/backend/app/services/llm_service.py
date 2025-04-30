import logging
from typing import Optional, List, Dict, Any
from uuid import UUID
from openai import OpenAI, OpenAIError
import json

from ..core.config import settings, LLMProvider
from ..models.game import GameState
from ..models.player import Player, Role, PlayerStatus
from ..models.actions import (
    BaseAction, MafiaKillAction, DoctorProtectAction, DetectiveInvestigateAction,
    ChatMessage, ActionType
)

logger = logging.getLogger(__name__)

class LLMServiceError(Exception):
    '''Custom exception for LLM service errors.'''
    pass

class LLMService:
    def __init__(self):
        self.client = None
        self.provider = settings.LLM_PROVIDER
        api_key = None

        if self.provider == LLMProvider.OPENAI:
            api_key = settings.OPENAI_API_KEY
            if api_key:
                self.client = OpenAI(api_key=api_key)
            else:
                logger.warning("OpenAI API key not found. LLMService will not function.")
        # TODO: Add initialization for other providers (Google, Anthropic)
        # elif self.provider == LLMProvider.GOOGLE:
        #     api_key = settings.GOOGLE_API_KEY
        #     # Initialize Google client
        # elif self.provider == LLMProvider.ANTHROPIC:
        #     api_key = settings.ANTHROPIC_API_KEY
        #     # Initialize Anthropic client

        if not self.client:
            logger.error(f"Failed to initialize LLM client for provider: {self.provider}")

    def _generate_night_action_prompt(self, ai_player: Player, game_state: GameState) -> str:
        '''Generates a detailed prompt for the LLM based on the game state and AI player's role for NIGHT ACTIONS.'''

        living_players = [p for p in game_state.players if p.status == PlayerStatus.ALIVE]
        player_list_str = "\n".join([f"- Player {p.id}: Status {p.status.value}" + (f" (You, Role: {ai_player.role.value})" if p.id == ai_player.id else "") for p in game_state.players])
        
        # Simplified history for now - enhance later with memory
        history_summary = "Game History Summary:\n" + "\n".join(game_state.history) if game_state.history else "No significant events yet."

        role_description = {
            Role.MAFIA: "You are a Mafia member. Your goal is to eliminate all Innocents. Choose one living player to kill tonight. Do not target yourself or other Mafia members (if known).",
            Role.DETECTIVE: "You are the Detective. Your goal is to identify Mafia members. Choose one living player to investigate tonight. You will learn if they are Mafia or Innocent.",
            Role.DOCTOR: "You are the Doctor. Your goal is to protect Innocents. Choose one living player to save tonight. If the Mafia targets them, your save will succeed. Consider protecting likely targets or yourself.",
            Role.VILLAGER: "You are a Villager. You have no special night action."
        }.get(ai_player.role, "Unknown role.")

        if ai_player.role == Role.VILLAGER:
            return "" # Villagers don't act at night

        # Identify potential targets (living players excluding self, maybe allies for Mafia)
        potential_targets = [p for p in living_players if p.id != ai_player.id]
        if ai_player.role == Role.MAFIA:
            # TODO: Incorporate knowledge of other Mafia members
            pass 
        
        if not potential_targets:
            logger.warning(f"AI Player {ai_player.id} ({ai_player.role.value}) has no valid targets.")
            return ""

        target_list_str = "\n".join([f"- Player {p.id}" for p in potential_targets])

        prompt = f"""
You are Player {ai_player.id}, an AI playing Mafia.
Your Role: {ai_player.role.value}
Your Objective: {role_description}

Game State:
Current Phase: Night {game_state.day_number}
Living Players: {len(living_players)}

Player List:
{player_list_str}

{history_summary}

Available Living Targets for Your Action:
{target_list_str}

Task: Decide your night action. Choose one player ID from the 'Available Living Targets' list.
Respond ONLY with a JSON object containing the key 'target_player_id' and the chosen player ID as the value. Example: {{"target_player_id": "player_uuid_here"}}
"""
        return prompt.strip()

    def determine_ai_night_action(self, ai_player: Player, game_state: GameState) -> Optional[BaseAction]:
        '''Uses the LLM to determine the night action for an AI player.'''
        if not self.client or ai_player.role == Role.VILLAGER:
            return None # No client initialized or Villager role

        prompt = self._generate_night_action_prompt(ai_player, game_state)
        if not prompt:
            return None # No action needed or no targets

        logger.info(f"Generating night action for AI Player {ai_player.id} ({ai_player.role.value}) using {self.provider.value}")
        logger.debug(f"LLM Prompt for Player {ai_player.id}:\n{prompt}")

        try:
            if self.provider == LLMProvider.OPENAI:
                # Using chat completions endpoint
                response = self.client.chat.completions.create(
                    model="gpt-3.5-turbo-0125", # Or configure via settings
                    messages=[
                        {"role": "system", "content": "You are an AI player in a game of Mafia."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7, # Allow some variability
                    max_tokens=50, # Should be enough for just the JSON
                    response_format={"type": "json_object"} # Request JSON output
                )
                response_content = response.choices[0].message.content
                logger.debug(f"LLM raw response for Player {ai_player.id}: {response_content}")

                if not response_content:
                    raise LLMServiceError("LLM returned empty content.")

                # Parse the JSON response
                action_data = json.loads(response_content)
                target_player_id_str = action_data.get('target_player_id')

                if not target_player_id_str:
                    raise LLMServiceError(f"LLM response missing 'target_player_id'. Response: {response_content}")

                # Validate target_player_id
                valid_target_ids = {p.id for p in game_state.players if p.status == PlayerStatus.ALIVE and p.id != ai_player.id}
                # TODO: Add Mafia ally check if needed
                
                target_player_uuid: Optional[UUID] = None
                try:
                    # Attempt to convert the string from LLM to UUID
                    potential_target_uuid = UUID(target_player_id_str)
                    if potential_target_uuid in valid_target_ids:
                        target_player_uuid = potential_target_uuid
                    else:
                         logger.warning(f"LLM for Player {ai_player.id} chose a valid UUID '{target_player_id_str}' but it's not among valid targets (living, not self). Falling back.")
                except ValueError:
                     logger.warning(f"LLM for Player {ai_player.id} provided a non-UUID target '{target_player_id_str}'. Falling back.")
                

                # If conversion failed or target is invalid, use fallback
                if target_player_uuid is None:
                    import random
                    if not valid_target_ids: # Should not happen if prompt generation worked
                         raise LLMServiceError(f"No valid targets available for Player {ai_player.id} ({ai_player.role.value}) fallback.")
                    target_player_uuid = random.choice(list(valid_target_ids))
                    logger.info(f"Fallback chose target {target_player_uuid} for Player {ai_player.id}")


                # Create the appropriate action object using the validated UUID
                action_args = {"player_id": ai_player.id, "target_id": target_player_uuid} # Use the validated UUID
                
                if ai_player.role == Role.MAFIA:
                    return MafiaKillAction(**action_args)
                elif ai_player.role == Role.DETECTIVE:
                    return DetectiveInvestigateAction(**action_args)
                elif ai_player.role == Role.DOCTOR:
                    return DoctorProtectAction(**action_args)
                else:
                    logger.error(f"Unexpected role {ai_player.role} attempted LLM action.")
                    return None

            # TODO: Add logic for other providers
            else:
                logger.warning(f"LLM provider {self.provider.value} not implemented yet.")
                return None

        except OpenAIError as e:
            logger.error(f"OpenAI API error for Player {ai_player.id}: {e}")
            raise LLMServiceError(f"OpenAI API error: {e}") from e
        except json.JSONDecodeError as e:
             logger.error(f"Failed to parse LLM JSON response for Player {ai_player.id}. Response: '{response_content}'. Error: {e}")
             raise LLMServiceError(f"Failed to parse LLM JSON response: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error during LLM action generation for Player {ai_player.id}: {e}")
            raise LLMServiceError(f"Unexpected error: {e}") from e

    def _generate_day_discussion_prompt(self, ai_player: Player, game_state: GameState, recent_messages: List[ChatMessage]) -> str:
        """Generates a prompt for the LLM for DAY discussion."""
        living_players = [p for p in game_state.players if p.status == PlayerStatus.ALIVE]
        player_list_str = "\n".join([f"- Player {p.id}: Status {p.status.value}" + (f" (You, Role: {ai_player.role.value})" if p.id == ai_player.id else "") for p in game_state.players])

        # Get recent history/announcements
        history_summary = "Recent Events/Announcements:\n" + "\n".join(game_state.history[-5:]) if game_state.history else "No recent events."

        # Get recent chat messages
        chat_summary = "Recent Chat Messages:\n"
        if recent_messages:
             chat_summary += "\n".join([f"- Player {msg.player_id}: {msg.message}" for msg in recent_messages[-10:]]) # Last 10 messages
        else:
            chat_summary += "No recent chat messages."

        # Role-specific goals/persona hints
        role_goal = {
            Role.MAFIA: "Your goal is to eliminate Innocents and avoid suspicion. Try to accuse others plausibly, deflect blame, or stay quiet.",
            Role.DETECTIVE: "Your goal is to identify Mafia. Use your investigation results subtly to guide Innocents or cast suspicion. Avoid revealing your role directly unless necessary.",
            Role.DOCTOR: "Your goal is to help Innocents win. Observe behavior and contribute to identifying Mafia. You might have saved someone last night.",
            Role.VILLAGER: "Your goal is to identify and lynch Mafia members. Discuss suspicions, ask questions, and analyze others' behavior."
        }.get(ai_player.role, "Your goal is to help your faction win.")

        # Include private info if Detective
        private_info = ""
        if ai_player.role == Role.DETECTIVE and ai_player.investigation_result:
            private_info = f"\nYour Private Information: {ai_player.investigation_result}"
        elif ai_player.role == Role.MAFIA:
            mafia_allies = [p.id for p in game_state.players if p.role == Role.MAFIA and p.id != ai_player.id and p.status == PlayerStatus.ALIVE]
            if mafia_allies:
                private_info = f"\nYour Mafia Allies (DO NOT REVEAL): {', '.join(map(str, mafia_allies))}"

        prompt = f"""
You are Player {ai_player.id}, an AI playing Mafia.
Your Role: {ai_player.role.value}
{role_goal}{private_info}

Game State:
Current Phase: Day {game_state.day_number} Discussion
Living Players: {len(living_players)}

Player List:
{player_list_str}

{history_summary}

{chat_summary}

Task: Generate a single, concise chat message (1-2 sentences) appropriate for the current discussion. Contribute to the conversation, express suspicion, defend yourself, or ask questions based on your role and the game state. Do not reveal your specific role unless strategically beneficial (rarely). Avoid overly generic statements.

Respond ONLY with a JSON object containing the key 'chat_message' and your message as a string value. Example: {{"chat_message": "I'm not sure about Player X, they seemed quiet last night."}}
"""
        return prompt.strip()

    def generate_ai_day_message(self, ai_player: Player, game_state: GameState) -> Optional[ChatMessage]:
        """Uses the LLM to generate a chat message for an AI player during the Day phase."""
        if not self.client:
            return None # No client initialized

        # Get recent chat context
        recent_chats = game_state.chat_history # Use the new field

        prompt = self._generate_day_discussion_prompt(ai_player, game_state, recent_chats)

        logger.info(f"Generating day message for AI Player {ai_player.id} ({ai_player.role.value}) using {self.provider.value}")
        logger.debug(f"LLM Day Prompt for Player {ai_player.id}:\n{prompt}")

        try:
            if self.provider == LLMProvider.OPENAI:
                response = self.client.chat.completions.create(
                    model="gpt-3.5-turbo-0125", # Or configure via settings
                    messages=[
                        {"role": "system", "content": "You are an AI player in a game of Mafia, participating in the day discussion."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.8, # Slightly higher for more varied discussion
                    max_tokens=100, # Allow longer messages than night actions
                    response_format={"type": "json_object"} # Request JSON output
                )
                response_content = response.choices[0].message.content
                logger.debug(f"LLM raw response for Player {ai_player.id} day message: {response_content}")

                if not response_content:
                    raise LLMServiceError("LLM returned empty content for day message.")

                # Parse the JSON response
                message_data = json.loads(response_content)
                message_text = message_data.get('chat_message')

                if not message_text or not message_text.strip():
                    logger.warning(f"LLM for Player {ai_player.id} returned empty or missing 'chat_message'. Response: {response_content}")
                    # Fallback or return None? For now, return None, phase logic can skip.
                    return None

                # Create the ChatMessage object
                return ChatMessage(player_id=ai_player.id, message=message_text.strip())

            # TODO: Add logic for other providers
            else:
                logger.warning(f"LLM provider {self.provider.value} not implemented yet for day messages.")
                return None

        except OpenAIError as e:
            logger.error(f"OpenAI API error during day message generation for Player {ai_player.id}: {e}")
            raise LLMServiceError(f"OpenAI API error: {e}") from e
        except json.JSONDecodeError as e:
             logger.error(f"Failed to parse LLM JSON response for Player {ai_player.id} day message. Response: '{response_content}'. Error: {e}")
             raise LLMServiceError(f"Failed to parse LLM JSON response: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error during day message generation for Player {ai_player.id}: {e}")
            raise LLMServiceError(f"Unexpected error: {e}") from e

# Global instance (consider dependency injection later if needed)
llm_service = LLMService() 