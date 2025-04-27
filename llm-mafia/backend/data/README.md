# Data Directory

This directory is used to store serialized game states in JSON format. Each game state is saved as a separate file with the game ID as the filename.

The files in this directory are not tracked by Git (see `.gitignore`), but the directory itself is necessary for the application to function properly.

## File Structure

- `{game_id}.json`: Serialized game state for a specific game 