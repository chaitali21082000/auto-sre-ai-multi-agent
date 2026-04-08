from vertexai.generative_models import GenerativeModel, Tool, FunctionDefinition
import vertexai
import json
import logging

logger = logging.getLogger(__name__)

vertexai.init(project="auto-sre-ai-multi-agent", location="us-central1")

model = GenerativeModel("gemini-2.5-flash")

def call_llm(prompt):
    """Simple LLM call without schema"""
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        logger.error(f"Error calling LLM: {e}")
        raise


def structured_call_llm(prompt, schema=None, system_instruction=None):
    """
    Call LLM with structured output matching a JSON schema.
    
    Args:
        prompt: The user prompt/query
        schema: JSON schema defining the expected response structure
        system_instruction: System prompt for the model
        
    Returns:
        Parsed JSON object matching the schema
    """
    try:
        # Build the prompt with schema
        schema_str = json.dumps(schema, indent=2) if schema else ""
        
        if system_instruction:
            # Use system instruction
            full_prompt = f"""{system_instruction}

{prompt}

Return your response as valid JSON matching this schema:
{schema_str}

IMPORTANT: Return ONLY valid JSON, no other text."""
        else:
            full_prompt = f"""{prompt}

Return your response as valid JSON matching this schema:
{schema_str}

IMPORTANT: Return ONLY valid JSON, no other text."""
        
        response = model.generate_content(full_prompt)
        response_text = response.text.strip()
        
        # Remove markdown code blocks if present
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        
        response_text = response_text.strip()
        
        # Parse JSON response
        parsed_response = json.loads(response_text)
        logger.info(f"Structured LLM response: {parsed_response}")
        return parsed_response
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM JSON response: {e}")
        logger.error(f"Response text: {response_text}")
        # Return error response matching schema structure
        if schema:
            default_response = {}
            for key, value_schema in schema.get("properties", {}).items():
                if value_schema.get("type") == "string":
                    default_response[key] = f"Error parsing response: {str(e)}"
                elif value_schema.get("type") == "number":
                    default_response[key] = 0
                elif value_schema.get("type") == "boolean":
                    default_response[key] = False
                elif value_schema.get("type") == "array":
                    default_response[key] = []
                elif value_schema.get("type") == "object":
                    default_response[key] = {}
            return default_response
        raise
    except Exception as e:
        logger.error(f"Error in structured LLM call: {e}")
        raise


def call_llm_with_functions(prompt, tools, system_instruction=None):
    """
    Call LLM with function/tool definitions for function calling.
    
    Args:
        prompt: The user prompt/query
        tools: List of tool/function definitions in MCP format
        system_instruction: System prompt for the model
        
    Returns:
        Dict with tool_calls if tools were invoked, or response text
    """
    try:
        # Convert MCP tool format to Vertex AI function definitions
        function_definitions = []
        for tool in tools:
            func_def = FunctionDefinition(
                name=tool.get("name"),
                description=tool.get("description"),
                parameters={
                    "type": "object",
                    "properties": tool.get("input_schema", {}).get("properties", {}),
                    "required": tool.get("input_schema", {}).get("required", [])
                }
            )
            function_definitions.append(func_def)
        
        # Create Tool with function definitions
        vertex_tool = Tool(function_declarations=function_definitions)
        
        # Build full prompt
        if system_instruction:
            full_prompt = f"""{system_instruction}

{prompt}"""
        else:
            full_prompt = prompt
        
        # Call model with tools
        response = model.generate_content(
            full_prompt,
            tools=[vertex_tool],
            tool_config={"function_calling_config": {"mode": "ANY"}}
        )
        
        # Check if tool was called
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if part.function_call:
                    logger.info(f"Tool called: {part.function_call.name}")
                    return {
                        "tool_calls": [{
                            "name": part.function_call.name,
                            "arguments": dict(part.function_call.args)
                        }],
                        "raw_response": response.text
                    }
        
        # No tool was called, return text response
        return {
            "tool_calls": [],
            "response": response.text
        }
        
    except Exception as e:
        logger.error(f"Error in LLM function calling: {e}")
        raise