"""
Manages loading and saving of application configuration data (e.g., shared folder, PIN hash).
"""
import json
import os
import logging

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_FILENAME = "config.json"

def save_config(config_data: dict, filepath: str = DEFAULT_CONFIG_FILENAME):
    """
    Saves the configuration dictionary to a JSON file.

    Args:
        config_data: The dictionary containing configuration to save.
        filepath: The path to the configuration file. Defaults to "config.json".
    """
    try:
        with open(filepath, 'w') as f:
            json.dump(config_data, f, indent=4)
        logger.info(f"Configuration saved successfully to {filepath}")
    except IOError as e:
        logger.error(f"IOError saving configuration to {filepath}: {e}", exc_info=True)
        # Potentially re-raise or handle more gracefully depending on application needs
    except Exception as e:
        logger.critical(f"An unexpected error occurred while saving configuration to {filepath}: {e}", exc_info=True)

def load_config(filepath: str = DEFAULT_CONFIG_FILENAME) -> dict:
    """
    Loads configuration from a JSON file.

    Returns an empty dict if the file doesn't exist or is invalid,
    or default values if applicable.

    Args:
        filepath: The path to the configuration file. Defaults to "config.json".

    Returns:
        A dictionary with the loaded configuration, or an empty dictionary if
        loading fails or the file doesn't exist.
    """
    if not os.path.exists(filepath):
        logger.info(f"Configuration file {filepath} not found. Returning empty config.")
        return {} 

    try:
        with open(filepath, 'r') as f:
            config_data = json.load(f)
            if not isinstance(config_data, dict):
                logger.warning(f"Invalid configuration format in {filepath}. Expected a dictionary, got {type(config_data)}. Returning empty config.")
                return {} 
            logger.info(f"Configuration loaded successfully from {filepath}")
            return config_data
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from {filepath}: {e}. Returning empty config.", exc_info=True)
        return {}
    except IOError as e:
        logger.error(f"IOError loading configuration from {filepath}: {e}. Returning empty config.", exc_info=True)
        return {}
    except Exception as e:
        logger.critical(f"An unexpected error occurred while loading configuration from {filepath}: {e}. Returning empty config.", exc_info=True)
        return {}

if __name__ == '__main__':
    # Example Usage
    test_config_path = "test_config.json"
    
    # Clean up previous test file if it exists
    if os.path.exists(test_config_path):
        os.remove(test_config_path)

    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
    # Test 1: Load non-existent config
    logger.info("Test 1: Loading non-existent config...")
    loaded_data = load_config(test_config_path)
    logger.info(f"Loaded data (should be empty): {loaded_data}")
    assert loaded_data == {}

    # Test 2: Save and Load
    logger.info("\nTest 2: Saving and loading config...")
    my_config = {
        "shared_folder_path": "/mnt/user/shared_files_test",
        "hashed_pin": "a1b2c3d4e5f6...",
        "theme": "dark"
    }
    save_config(my_config, test_config_path)
    loaded_data = load_config(test_config_path)
    logger.info(f"Loaded data: {loaded_data}")
    assert loaded_data == my_config

    # Test 3: Load config with invalid JSON
    logger.info("\nTest 3: Loading config with invalid JSON...")
    with open(test_config_path, 'w') as f:
        f.write("this is not valid json")
    loaded_data = load_config(test_config_path)
    logger.info(f"Loaded data (should be empty): {loaded_data}")
    assert loaded_data == {}

    # Test 4: Load config with valid JSON but not a dictionary (e.g. a list)
    logger.info("\nTest 4: Loading config with JSON that is not a dictionary...")
    with open(test_config_path, 'w') as f:
        json.dump([1, 2, 3], f)
    loaded_data = load_config(test_config_path)
    logger.info(f"Loaded data (should be empty): {loaded_data}")
    assert loaded_data == {}
    
    # Clean up
    if os.path.exists(test_config_path):
        os.remove(test_config_path)
    logger.info("\nConfig manager tests finished.")
