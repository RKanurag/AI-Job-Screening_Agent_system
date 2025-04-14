# utils/config_loader.py
import yaml
from pathlib import Path

CONFIG_FILE = Path(__file__).parent.parent / "config.yaml" # Point to root config.yaml

def load_config():
    """Loads the configuration from config.yaml."""
    if not CONFIG_FILE.is_file():
        raise FileNotFoundError(f"Configuration file not found at {CONFIG_FILE}")
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = yaml.safe_load(f)
        # Basic validation (add more as needed)
        required_keys = ['ollama_model', 'database_path', 'shortlisting_threshold', 'cv_directory', 'jd_csv_path']
        if not all(key in config for key in required_keys):
            raise ValueError("Missing one or more required keys in config.yaml")
        return config
    except Exception as e:
        print(f"Error loading configuration: {e}")
        # Provide default fallback or raise the error
        raise  # Re-raise the exception after printing

# Example usage (optional, for testing)
if __name__ == '__main__':
    try:
        config = load_config()
        print("Configuration loaded successfully:")
        print(config)
    except Exception as e:
        print(f"Failed to load configuration: {e}")