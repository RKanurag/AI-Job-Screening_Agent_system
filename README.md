
# Job Screening Agent System

This project is a job screening agent system designed to process and analyze job descriptions and candidate CVs using advanced language models. It provides tools for extracting, summarizing, and matching candidate profiles to job requirements.
# LIVE-DEMO
https://ai-job-screening-agent-system.onrender.com

## Requirements

To run this project locally, you will need:

- Python 3.8 or higher
- All dependencies listed in `requirements.txt`
- [Ollama](https://ollama.com/) (or "Olama") installed on your local machine for running LLMs locally

Install Python dependencies with:
```bash
pip install -r requirements.txt
```

### Local LLM Processing

The developer has installed Ollama on their local machine to extract content from the provided dataset. This setup allows the project to process data using locally hosted language models, ensuring privacy and reducing costs.

### Cloud Deployment / Online Hosting

If you want to host the project online and perform LLM processing on a cloud machine, you have two main options:

1. **Purchase or use an API key for a cloud-based LLM provider** (e.g., OpenAI, Anthropic, or any other LLM API). This allows the project to send data to the cloud for processing.
2. **Use a paid cloud service** to run Ollama or another LLM server, and configure the project to connect to it.

> **Note:** Using cloud APIs may incur significant costs depending on usage and the provider's pricing.

## Live Demo / Current Deployment

The current deployment (or live demo) uses preprocessed data. The developer has installed Ollama on their local machine to fetch and process data from the dataset. As a result, the demo showcases results generated using locally processed data.

## Data

- All datasets (CVs and job descriptions) are located in the `data/` directory.
- Preprocessing scripts and agents are provided in the `agents/` directory.

## Running the Project

1. Ensure you have Python and Ollama installed locally.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the main application:
   ```bash
   python main.py
   ```
4. For UI, navigate to the `ui/` directory and run:
   ```bash
   python app.py
   ```

## Customization

- To use a cloud LLM API, update the configuration in `config.yaml` with your API key and endpoint.
- For local LLM processing, ensure Ollama is running and accessible.

## License

This project is for educational and research purposes. Please review the LICENSE file for more details.

# For cloud deployment
To deploy this project on the cloud and use a cloud-based LLM (such as OpenAI, Anthropic, or any other provider), you do not need to change any code. The only change required is to update the config.yaml file with your cloud LLM provider's details.

Here is an example of what your config.yaml might look like for OpenAI:

llm_provider: openai
api_key: `YOUR_OPENAI_API_KEY`
api_base_url: `https://api.openai.com/v1`
model: `gpt-3.5-turbo`
Instructions:

Replace YOUR_OPENAI_API_KEY with your actual API key from your cloud LLM provider.
Adjust the model and api_base_url fields as needed for your specific provider and model.
