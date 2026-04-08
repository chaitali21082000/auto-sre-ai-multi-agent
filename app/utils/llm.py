from vertexai.generative_models import GenerativeModel, Tool
import vertexai
import json
import logging
import os

logger = logging.getLogger(__name__)

project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "auto-sre-ai-multi-agent-492710")
vertexai.init(project=project_id, location="us-central1")

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
    Falls back to text-based approach if function calling not available.
    
    Args:
        prompt: The user prompt/query
        tools: List of tool/function definitions in MCP format
        system_instruction: System prompt for the model
        
    Returns:
        Dict with tool_calls if tools were invoked, or response text
    """
    try:
        logger.info("Attempting function calling with Vertex AI tools")
        
        # Build tool definitions
        tool_definitions = []
        for tool in tools:
            tool_def = {
                "name": tool.get("name"),
                "description": tool.get("description"),
                "parameters": {
                    "type": "object",
                    "properties": tool.get("input_schema", {}).get("properties", {}),
                    "required": tool.get("input_schema", {}).get("required", [])
                }
            }
            tool_definitions.append(tool_def)
        
        # Try to use Vertex AI tool calling if available
        try:
            from google.ai.generativelanguage import FunctionDeclaration
            
            function_declarations = []
            for tool_def in tool_definitions:
                func_decl = FunctionDeclaration(
                    name=tool_def["name"],
                    description=tool_def["description"],
                    parameters={
                        "type_": "OBJECT",
                        "properties": tool_def["parameters"]["properties"],
                        "required": tool_def["parameters"]["required"]
                    }
                )
                function_declarations.append(func_decl)
            
            vertex_tool = Tool(function_declarations=function_declarations)
            
            # Build full prompt
            if system_instruction:
                full_prompt = f"""{system_instruction}

{prompt}"""
            else:
                full_prompt = prompt
            
            # Call model with tools
            response = model.generate_content(full_prompt, tools=[vertex_tool])
            
            # Check if tool was called
            if response.candidates and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'function_call') and part.function_call:
                        logger.info(f"Tool called: {part.function_call.name}")
                        return {
                            "tool_calls": [{
                                "name": part.function_call.name,
                                "arguments": dict(part.function_call.args) if hasattr(part.function_call, 'args') else {}
                            }],
                            "raw_response": response.text
                        }
            
            logger.info("No tool was called, returning text response")
            return {
                "tool_calls": [],
                "response": response.text
            }
            
        except ImportError:
            logger.warning("FunctionDeclaration not available, using text-based fallback")
            raise  # Fall through to text-based approach
        
    except Exception as e:
        logger.warning(f"Function calling failed: {e}, using text-based fallback")
        
        # Fallback: text-based tool invocation
        try:
            tool_names = ", ".join([t.get("name") for t in tools])
            tool_descriptions = "\n".join([f"- {t.get('name')}: {t.get('description')}" for t in tools])
            
            if system_instruction:
                fallback_prompt = f"""{system_instruction}

{prompt}

Available tools:
{tool_descriptions}

If you need to use a tool, respond with a JSON object like:
{{"tool_name": "tool_name_here", "arguments": {{"key": "value"}}}}

Otherwise respond normally with your analysis/response."""
            else:
                fallback_prompt = f"""{prompt}

Available tools:
{tool_descriptions}

If you need to use a tool, respond with JSON like {{"tool_name": "name", "arguments": {{}}}}.
Otherwise respond normally."""
            
            response = model.generate_content(fallback_prompt)
            response_text = response.text.strip()
            
            # Try to parse as tool call
            try:
                # Check if response looks like JSON
                if response_text.startswith("{"):
                    parsed = json.loads(response_text)
                    if "tool_name" in parsed and "arguments" in parsed:
                        return {
                            "tool_calls": [{
                                "name": parsed["tool_name"],
                                "arguments": parsed.get("arguments", {})
                            }],
                            "fallback": True
                        }
            except (json.JSONDecodeError, ValueError):
                pass
            
            # If not a tool call, return as text response
            return {
                "tool_calls": [],
                "response": response_text,
                "fallback": True
            }
            
        except Exception as fallback_error:
            logger.error(f"Text-based fallback also failed: {fallback_error}")
            return {
                "tool_calls": [],
                "response": "",
                "error": str(fallback_error)
            }