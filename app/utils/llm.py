from vertexai.generative_models import GenerativeModel
import vertexai

vertexai.init(project="auto-sre-ai-multi-agent", location="us-central1")

model = GenerativeModel("gemini-2.5-flash")

def call_llm(prompt):
    response = model.generate_content(prompt)
    return response.text