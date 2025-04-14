# utils/llm_utils.py
import ollama
import json
from .config_loader import load_config # Use relative import

# Load config once when module is imported
try:
    config = load_config()
    OLLAMA_MODEL = config.get('ollama_model', 'mistral') # Default to mistral if not set
    # Ollama library uses OLLAMA_HOST env var, or defaults.
    # If you need to override via config, you might need direct API calls or set env var.
    print(f"LLM Util configured to use model: {OLLAMA_MODEL}")
except Exception as e:
    print(f"CRITICAL: Failed to load config for LLM utils: {e}. Using defaults.")
    OLLAMA_MODEL = 'mistral'


def generate_text(prompt: str, system_message: str = None, format: str = None) -> str:
    """
    Generates text using the configured Ollama model.

    Args:
        prompt: The user's prompt.
        system_message: An optional system message to guide the AI's behavior.
        format: Optional format constraint for the output (e.g., 'json').

    Returns:
        The generated text content as a string, or an empty string on error.
    """
    messages = []
    if system_message:
        messages.append({'role': 'system', 'content': system_message})
    messages.append({'role': 'user', 'content': prompt})

    try:
        # Use ollama.chat for conversational models
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=messages,
            format=format # Pass format if specified
        )
        generated_content = response['message']['content']
        print(f"LLM ({OLLAMA_MODEL}) generated response successfully.")
        return generated_content.strip()

    except Exception as e:
        print(f"Error calling Ollama model {OLLAMA_MODEL}: {e}")
        # Consider more specific error handling (e.g., connection errors)
        return "" # Return empty string on error

def generate_structured_output(prompt: str, system_message: str = None) -> dict | None:
    """
    Generates text and attempts to parse it as JSON.

    Args:
        prompt: The user's prompt, designed to elicit JSON output.
        system_message: Optional system message (e.g., "You are a helpful assistant outputting JSON.")

    Returns:
        A dictionary parsed from the JSON response, or None on error or if parsing fails.
    """
    # Instruct the model to output JSON
    if not system_message:
         system_message = "You are an AI assistant. Respond ONLY with valid JSON that adheres to the requested structure. Do not include any explanatory text before or after the JSON."
    else:
         system_message += "\nRespond ONLY with valid JSON. No extra text."

    # Add instruction for JSON output directly in prompt if model struggles
    json_prompt = f"{prompt}\n\nOutput the result as a valid JSON object."

    # Use the format='json' parameter if supported by the model/Ollama version
    raw_response = generate_text(json_prompt, system_message, format='json')

    if not raw_response:
        return None

    try:
        # Clean potential markdown code fences ```json ... ```
        if raw_response.startswith("```json"):
            raw_response = raw_response[7:]
        if raw_response.endswith("```"):
            raw_response = raw_response[:-3]

        parsed_json = json.loads(raw_response.strip())
        print("Successfully parsed LLM response as JSON.")
        return parsed_json
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from LLM response: {e}")
        print(f"Raw response was: ---{raw_response}---")
        return None # Indicate parsing failure
    except Exception as e:
        print(f"An unexpected error occurred during JSON parsing: {e}")
        return None


# --- Example Usage (optional, for testing) ---
if __name__ == '__main__':
    print("\n--- Testing LLM Text Generation ---")
    test_prompt = "Explain the concept of a multi-agent system in 2 sentences."
    response_text = generate_text(test_prompt, system_message="You are a helpful AI assistant.")
    if response_text:
        print(f"LLM Response:\n{response_text}")
    else:
        print("LLM text generation failed.")

    print("\n--- Testing LLM Structured Output (JSON) ---")
    test_json_prompt = "Extract the name and primary skill from this text: 'John Doe is a Python expert.'"
    # Clearly define the desired JSON structure in the prompt or system message for complex cases
    response_json = generate_structured_output(test_json_prompt, system_message="Output JSON like {'name': '...', 'skill': '...'}")

    if response_json:
        print(f"LLM JSON Response:\n{response_json}")
        # Example validation
        if isinstance(response_json, dict) and 'name' in response_json and 'skill' in response_json:
             print("JSON structure appears valid.")
        else:
             print("Warning: JSON structure might be incorrect.")
    else:
        print("LLM JSON generation or parsing failed.")