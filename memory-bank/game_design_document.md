# Game Design Document: Mafia - LLM Edition (Single Player)

**Version:** 1.0
**Date:** 2025-04-27

## 1. Overview

### 1.1. Game Concept
Mafia - LLM Edition is a single-player, web-based adaptation of the classic social deduction party game "Mafia" (also known as "Werewolf"). The player takes on one role within a town populated by other characters controlled by Large Language Model (LLM) agents. The player must use deduction, observation of AI behavior, and communication (via text input) to help their faction (Innocents or Mafia) win.

### 1.2. Target Audience
Players who enjoy social deduction games, logic puzzles, AI interaction, and single-player experiences.

### 1.3. Core Gameplay Loop
The game alternates between **Night** and **Day** phases.
* **Night:** Special roles (Mafia, Detective, Doctor) perform their actions secretly.
* **Day:** Events of the night are announced. Players (human and AI) discuss, accuse, and defend themselves. A vote is held to lynch a suspected Mafia member.
This cycle repeats until a win condition is met.

### 1.4. Win Conditions
* **Innocents (Villagers, Detective, Doctor) Win:** All Mafia members are eliminated.
* **Mafia Wins:** The number of Mafia members is equal to or greater than the number of Innocent members remaining.

## 2. Game Mechanics

### 2.1. Game Setup
1.  **Player Count:** The human player chooses the total number of players in the game (e.g., 7, 9, 11). Let this be 'N'.
2.  **Role Assignment:**
    * Roles are assigned randomly to the N players (1 human, N-1 AI).
    * Standard Role Distribution (Example for 9 players):
        * 2 Mafia
        * 1 Detective
        * 1 Doctor
        * 5 Villagers
    * The human player is informed of their assigned role and, if Mafia, the identity of other Mafia members. AI agents are internally aware of their roles and allies (if Mafia).

### 2.2. Roles
* **Mafia:**
    * Knows who the other Mafia members are.
    * During the Night phase, collectively decides (via internal AI logic/communication) on one player to eliminate.
* **Detective (Innocent):**
    * During the Night phase, chooses one player to investigate.
    * Learns whether the investigated player is Mafia or Innocent (cannot distinguish between different Innocent roles).
* **Doctor (Innocent):**
    * During the Night phase, chooses one player to protect from elimination.
    * If the protected player is targeted by the Mafia that night, the kill fails.
    * (Optional Rule: Cannot protect the same player two nights in a row).
    * (Optional Rule: Cannot self-protect).
* **Villager (Innocent):**
    * No special night actions.
    * Must participate in Day phase discussions and voting to identify and lynch Mafia members.

### 2.3. Phases

#### 2.3.1. Night Phase
1.  The game interface indicates it's Night.
2.  **Mafia Action:** If the human player is Mafia, they propose/vote on a target with AI Mafia members (interface TBD). If AI only, they decide internally. The chosen target is marked for elimination.
3.  **Detective Action:** If the human player is the Detective, they choose a player to investigate. If AI, it chooses based on its logic. The result is stored (revealed to the Detective at the start of the Day).
4.  **Doctor Action:** If the human player is the Doctor, they choose a player to protect. If AI, it chooses based on its logic.
5.  Phase ends when all actions are submitted/processed.

#### 2.3.2. Day Phase
1.  **Announcements:**
    * The game announces who was killed during the night (if anyone, considering Doctor protection). The role of the killed player is revealed.
    * If the human is the Detective, they privately receive the result of their investigation.
2.  **Discussion:**
    * A timed period (or turn-based) for discussion.
    * The human player can type messages into a chat interface.
    * AI agents generate dialogue based on their role, persona, available information (public knowledge, private knowledge like investigation results or Mafia team), and strategic goals.
    * AI dialogue should include accusations, defenses, questions, and attempts to deduce/deceive.
3.  **Voting:**
    * After discussion, a voting period begins.
    * Each living player (human and AI) votes to lynch one player.
    * The human player selects a target via the UI.
    * AI agents vote based on their internal logic, suspicions, and faction goals.
4.  **Lynching:**
    * The player receiving the most votes is lynched. Ties may result in no lynching or a revote (TBD).
    * The role of the lynched player is revealed.
5.  **Check Win Condition:** The game checks if a win condition has been met. If so, the game ends. Otherwise, the cycle repeats starting with the Night phase.

## 3. AI Agent Behavior (LLM Integration)

### 3.1. Core Requirements
* **Role Adherence:** AI must act consistently with its assigned role (e.g., Mafia deflects suspicion, Detective subtly guides innocents, Doctor protects key targets, Villagers try to deduce).
* **Persona:** Each AI should have a basic, persistent personality (e.g., quiet, aggressive, logical, nervous) that influences its dialogue style. This can be randomly assigned at the start.
* **Memory:** AI must retain key information across phases:
    * Its own role and allies (if Mafia).
    * Public knowledge: Who died, who got lynched, revealed roles, voting records, public accusations.
    * Private knowledge: Detective investigation results, Mafia targets.
* **Strategic Reasoning:** AI needs logic for:
    * **Target Selection (Mafia):** Prioritize perceived threats (Detective, influential speakers), avoid suspicion.
    * **Investigation (Detective):** Target suspicious players, quiet players, or accusers.
    * **Protection (Doctor):** Protect self, likely targets (known Detective, players accused by Mafia), or strategically valuable players.
    * **Discussion:** Generate plausible arguments, accusations, defenses based on available information and role goals. Use persona.
    * **Voting:** Vote based on deduction, suspicion, alliances (Mafia), or self-preservation.

### 3.2. LLM Prompting Strategy
* Each AI agent's "turn" (speaking, voting, night action) will involve querying an LLM API.
* The prompt must include:
    * Game rules overview.
    * Current game state (living players, dead players, revealed roles, day/night number).
    * The AI's assigned role and persona.
    * The AI's memory (private knowledge, summary of previous relevant events/dialogue).
    * The current task (e.g., "Discuss who you suspect and why," "Vote for one player to lynch," "Choose a player to investigate").
* The game backend needs to parse the LLM response (dialogue, vote choice, action target) and integrate it into the game state. Error handling for invalid/nonsensical responses is crucial.

## 4. User Interface (UI) & User Experience (UX)

### 4.1. Main Screen Layout
* **Player List:** Shows all players (AI and human), their status (alive/dead), and revealed roles (if dead). Maybe simple avatars.
* **Game Log / Chat:** Displays game events (deaths, lynches, phase changes) and dialogue from all players.
* **Input Area:** Text box for the human player to enter messages during the Day phase discussion.
* **Action Area:** Context-sensitive area for night actions (if applicable to human role) or voting buttons during the Day phase.
* **Game State Info:** Current phase (Day/Night), Day number, players remaining.

### 4.2. Interaction Flow
* Clear visual cues for phase transitions.
* Intuitive interface for submitting night actions (e.g., clicking on a player name).
* Simple voting mechanism (e.g., buttons next to player names in the list).
* Human player's role and relevant private information clearly displayed (but only to them).
* AI messages appear in the chat log, identified by the AI player's name/avatar.

## 5. Future Enhancements

* Additional roles (Vigilante, Bodyguard, Jester, Executioner, etc.).
* Customizable AI personas and difficulty levels.
* Different map themes or scenarios.
* More sophisticated AI memory and long-term strategy.
* Visual aids for deduction (e.g., relationship graphs, suspicion meters).
* Player statistics and history.
* Option for human players to replace AI (multiplayer mode).