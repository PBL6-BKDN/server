import ast
import asyncio
from contextlib import asynccontextmanager
import inspect
import json
import os
from pprint import pformat
import re
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI
from mcp_custom.mcp_client import FunctionDefinition, MCPFunctionClient
from log import setup_logger
from config import LLM_API_KEY, LLM_MODEL, LLM_BASE_URL

logger = setup_logger(__name__)


class Agent:
    def __init__(
        self,
        base_url=None,
        api_key=None,
        model=None,
        temperature=0.7,
        extra_headers: Optional[Dict[str, str]] = None,
        system_prompt: Optional[str] = None,
        mcp_config: Optional[Dict[str, Any]] = None
    ):
        self.base_url = base_url or os.environ.get("LLM_BASE_URL")
        self.api_key = api_key or os.environ.get("LLM_API_KEY")
        self.model = model or os.environ.get("LLM_MODEL")

        if not self.base_url:
            raise ValueError(
                "LLM base_url must be provided or set via LLM_BASE_URL")
        if not self.model:
            raise ValueError("Model must be provided or set via LLM_MODEL")

        # Compose default headers to avoid Cloudflare blocking by UA/challenge
        default_headers: Dict[str, str] = {
            "User-Agent": os.environ.get("LLM_USER_AGENT", "curl/8.4.0"),
            "Accept": "application/json",
        }

        if extra_headers:
            default_headers.update(extra_headers)

        self.client = AsyncOpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            default_headers=default_headers,
        )
        self.temperature = temperature
        self.functions: List[FunctionDefinition] = []
        self.mcp_client = MCPFunctionClient(mcp_config) if mcp_config else None
        self._system_prompt = system_prompt

    def _parse_function_calls(self, response: str) -> List[Dict[str, Any]]:
        # Giống GemmaMCPClient._parse_function_calls
        response = response.strip()
        if not response or not (
            response.startswith(
                "```tool_code")
            and response.endswith("```")
        ):
            return []
        try:
            cleaned_response = (
                response.lstrip("```tool_code").rstrip("```").strip()
            )
            parsed = ast.parse(cleaned_response, mode="eval")
            if not isinstance(parsed.body, ast.List):
                return []
            function_calls: List[Dict[str, Any]] = []
            for node in parsed.body.elts:
                if not isinstance(node, ast.Call):
                    continue
                func_name = node.func.id
                args_dict: Dict[str, Any] = {}
                for kw in node.keywords:
                    try:
                        value = ast.literal_eval(kw.value)
                    except (ValueError, SyntaxError):
                        value = ast.unparse(kw.value)
                    args_dict[kw.arg] = value
                if node.args:
                    matching_func = next(
                        (f for f in self.functions if f.name == func_name), None)
                    if matching_func:
                        required_params = matching_func.required
                        for i, arg in enumerate(node.args):
                            if i < len(required_params):
                                try:
                                    value = ast.literal_eval(arg)
                                except (ValueError, SyntaxError):
                                    value = ast.unparse(arg)
                                args_dict[required_params[i]] = value
                function_calls.append(
                    {"name": func_name, "arguments": args_dict})
            return function_calls
        except (SyntaxError, AttributeError, ValueError):
            pattern = r"(\w+)\((.*?)\)"
            matches = re.findall(pattern, response)
            function_calls: List[Dict[str, Any]] = []
            for func_name, args_str in matches:
                args_dict: Dict[str, Any] = {}
                if args_str.strip():
                    current_key = None
                    current_value: List[str] = []
                    in_string = False
                    string_char = None
                    for char in args_str + ",":
                        if char in "\"'":
                            if not in_string:
                                in_string = True
                                string_char = char
                            elif char == string_char:
                                in_string = False
                        elif char == "," and not in_string:
                            if current_key and current_value:
                                args_dict[current_key.strip()] = "".join(
                                    current_value).strip()
                            current_key = None
                            current_value = []
                        elif char == "=" and not in_string and not current_key:
                            current_key = "".join(current_value)
                            current_value = []
                        else:
                            current_value.append(char)
                function_calls.append(
                    {"name": func_name, "arguments": args_dict})
            return function_calls

    def _build_prompt(self) -> str:
        if not self.functions:
            return self._system_prompt
        functions_json = json.dumps([f.to_dict()
                                    for f in self.functions], indent=2)
        return self._system_prompt + "\n\n" + """Bạn cũng là một trợ lý. Bạn có quyền sử dụng các công cụ có sẵn để thực hiện các
tác vụ. Nếu bạn quyết định sử dụng các công cụ có sẵn,
bạn phải đặt nó trong định dạng danh sách của:

```tool_code
[func_name1(params_name1=params_value1, params_name2=params_value2...), func_name2(params)]
```

Bạn KHÔNG ĐƯỢC bao gồm bất kỳ văn bản nào khác trong câu trả lời nếu bạn gọi một công cụ.
Nếu bạn không cần gọi bất kỳ công cụ nào, hãy trả lời bình thường.

Sau đây là các công cụ có sẵn:
""" + functions_json
        

    async def _register_mcp_tools(self) -> None:
        if not self.mcp_client:
            return
        for tool_name, tool_info in self.mcp_client.tools.items():
            tool = tool_info["tool"]
            function_def = FunctionDefinition(
                name=tool_name,
                description=tool.description or "No description provided.",
                parameters={
                    "type": "object",
                    "properties": tool.inputSchema.get("properties", {}),
                    "required": tool.inputSchema.get("required", []),
                },
                required=tool.inputSchema.get("required", []),
            )
            self.functions.append(function_def)

    async def chat(
        self,
        message: str,
        execute_functions: bool = False,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> str | List[Dict[str, Any]] | Dict:
        try:
            messages: List[Dict[str, str]] = []
            messages.append(
                {"role": "system", "content": self._build_prompt()})
            if history:
                messages.extend(history)
            messages.append({"role": "user", "content": message})
            logger.debug(f"call agent with message:\n{pformat(messages)} with chat history: {pformat(history)}")

            resp = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
            )
            text = resp.choices[0].message.content or ""
            logger.debug(f"Agent response: {pformat(text)}")
            function_calls = self._parse_function_calls(text)
            if function_calls:
                if not execute_functions:
                    return function_calls
                else:
                    results = []
                    for func_call in function_calls:
                        result = await self.execute_function(func_call["name"], func_call["arguments"])
                        results.append(
                            {"name": func_call["name"], "result": result})
                    # call model again with results as context to generate final answer
                    followup_history = (history or []) + [
                        {"role": "user", "content": message},
                        {"role": "assistant", "content": text},
                    ]
                    return await self.chat(
                        json.dumps(results, indent=2),
                        execute_functions=execute_functions,
                        history=followup_history,
                    )

            return text
        except Exception as e:
            logger.error(f"Agent chat error: {e}")
            return f"Lỗi khi chat: {e}"

    async def chat_stream(
        self,
        message: str,
        history: Optional[List[Dict[str, str]]] = None,
    ):
        """
        Stream câu trả lời từng chunk text (không hỗ trợ function calling trong chế độ stream).

        Trả về async generator yield ra các đoạn text (có thể là token/đoạn).
        """
        messages: List[Dict[str, str]] = []
        messages.append({"role": "system", "content": self._build_prompt()})
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": message})

        try:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                stream=True,
            )
            async for part in stream:
                try:
                    delta = part.choices[0].delta.content if hasattr(part.choices[0], "delta") else None
                    if delta:
                        yield delta
                except Exception:
                    # Bỏ qua chunk không hợp lệ
                    continue
        except Exception as e:
            logger.error(f"Agent chat_stream error: {e}")
            return

    async def execute_function(
        self,
        func_name: str,
        arguments: Dict[str, Any]
    ) -> Any:
        logger.debug(
            f"Executing function: {func_name} with arguments: {arguments}")
        if self.mcp_client and func_name in (self.mcp_client.tools.keys() if self.mcp_client.tools else []):
            return await self.mcp_client.execute_tool(func_name, arguments)

        func_def = next(
            (f for f in self.functions if f.name == func_name), None)

        if not func_def or not func_def.callable:
            raise ValueError(f"No callable found for function {func_name}")

        output = await func_def.callable(**arguments) if inspect.iscoroutinefunction(func_def.callable) else func_def.callable(**arguments)

        logger.debug(f"Function {func_name} returned: {output}")
        return output

    async def initialize(self) -> None:
        if self.mcp_client:
            await self.mcp_client.initialize()
            await self._register_mcp_tools()

    async def cleanup(self) -> None:
        if self.mcp_client:
            await self.mcp_client.cleanup()

    @asynccontextmanager
    async def managed(self):
        try:
            await self.initialize()
            yield self
        finally:
            await self.cleanup()


async def main():
    mcp_config = {
        "mcpServers": {
            "PBL6_MCP_Server": {
                "type": "sse",
                "url": "http://localhost:8000/sse"
            }
        }
    }

    client = Agent(
        base_url=LLM_BASE_URL,
        api_key=LLM_API_KEY,
        model=LLM_MODEL,
        mcp_config=mcp_config
    )
    async with client.managed():
        reply = await client.chat("Bây giờ là mấy giờ rồi?", execute_functions=True)
        logger.info(f"Agent reply: {reply}")

if __name__ == "__main__":
    asyncio.run(main())
