"""
Hệ thống đa agent kết hợp để xử lý yêu cầu từ người dùng
"""
import asyncio
import json
import os
from pprint import pformat
import time
import uuid
from typing import AsyncGenerator, Dict, List, Any, Optional

from agent import Agent
from agent_tools import get_search_tools, get_task_tools
from log import setup_logger
from mcp_custom.service.tts import generate_tts

logger = setup_logger(__name__)

class AgentType:
    COORDINATOR = "coordinator"
    SEARCH = "search"
    TASK = "task"
    RESPONSE = "response"
    PLANNER = "planner"

class MultiAgentSystem:
    def __init__(self, base_url=None, api_key=None, model=None):
        """
        Khởi tạo hệ thống đa agent
        
        Args:
            base_url: URL của LLM API
            api_key: API key của LLM
            model: Tên model LLM
        """
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        
        # Khởi tạo các agent
        self.agents = {}
        self.init_agents()
        
    def init_agents(self):
        """
        Khởi tạo các agent trong hệ thống
        """
        # Agent planner 
        self.agents[AgentType.PLANNER] = Agent(
            base_url=self.base_url,
            api_key=self.api_key,
            model=self.model,
            system_prompt="""
Bạn là Planner. Lập kế hoạch BƯỚC KẾ TIẾP dưới dạng JSON thuần, một đối tượng duy nhất.
Các giá trị hợp lệ cho step_type: 'search', 'task', 'answer', 'clarify'.
- Nếu đã đủ thông tin để trả lời, dùng step_type='answer'.
- Nếu cần thông tin, dùng 'search'. Nếu cần thực hiện hành động, dùng 'task'.
"Schema: {{
    "step_type": str, 
    "goal": str, 
    "inputs": object, 
    "success_criteria": [str]
}}
""")
        # Agent điều phối
        self.agents[AgentType.COORDINATOR] = Agent(
            base_url=self.base_url,
            api_key=self.api_key,
            model=self.model,
            system_prompt="""
Bạn là agent điều phối, có nhiệm vụ phân tích yêu cầu của người dùng và quyết định cần chuyển yêu cầu đến agent nào để xử lý.
            
Bạn sẽ nhận được một đoạn văn bản là kết quả chuyển đổi từ giọng nói sang văn bản. Nhiệm vụ của bạn là:
1. Phân tích nội dung yêu cầu
2. Xác định loại yêu cầu (tìm kiếm thông tin, thực hiện tác vụ, trả lời câu hỏi, v.v.)
3. Quyết định chuyển yêu cầu đến agent phù hợp

Các agent có sẵn:
- search: Tìm kiếm thông tin từ internet hoặc cơ sở dữ liệu
- task: Thực hiện các tác vụ cụ thể (điều khiển thiết bị, thực hiện hành động)
- response: Tạo câu trả lời tự nhiên, thân thiện cho người dùng

Bạn phải trả về kết quả dưới dạng JSON với định dạng sau:
{
  "agent": "tên_agent",
  "request": "nội_dung_yêu_cầu_đã_làm_rõ"
}

Trong đó:
- tên_agent: là một trong các giá trị "search", "task", "response"
- nội_dung_yêu_cầu_đã_làm_rõ: là yêu cầu của người dùng đã được làm rõ"""
        )
        
        # Agent tìm kiếm thông tin
        search_agent = Agent(
            base_url=self.base_url,
            api_key=self.api_key,
            model=self.model,
            system_prompt="""Bạn là agent tìm kiếm thông tin, có nhiệm vụ tìm kiếm và tổng hợp thông tin từ internet hoặc cơ sở dữ liệu.
            
Bạn sẽ nhận được một yêu cầu tìm kiếm thông tin. Nhiệm vụ của bạn là:
1. Phân tích yêu cầu tìm kiếm
2. Tìm kiếm thông tin liên quan bằng cách sử dụng các công cụ có sẵn
3. Tổng hợp và trả về thông tin chính xác, ngắn gọn

Hãy đảm bảo thông tin bạn cung cấp là chính xác, cập nhật và đáng tin cậy."""
        )
        
        # Thêm công cụ tìm kiếm cho search agent
        search_tools = get_search_tools()
        for tool in search_tools:
            search_agent.functions.append(tool)
        
        self.agents[AgentType.SEARCH] = search_agent
        
        # Agent thực hiện tác vụ
        task_agent = Agent(
            base_url=self.base_url,
            api_key=self.api_key,
            model=self.model,
            system_prompt="""Bạn là agent thực hiện tác vụ, có nhiệm vụ xử lý các yêu cầu liên quan đến thực hiện hành động cụ thể.
            
Bạn sẽ nhận được một yêu cầu thực hiện tác vụ. Nhiệm vụ của bạn là:
1. Phân tích yêu cầu và xác định hành động cần thực hiện
2. Thực hiện hành động thông qua các công cụ có sẵn
3. Báo cáo kết quả thực hiện

Hãy đảm bảo thực hiện đúng và đầy đủ yêu cầu của người dùng."""
        )
        
        # Thêm công cụ thực hiện tác vụ cho task agent
        task_tools = get_task_tools()
        task_agent.functions.extend(task_tools)

        self.agents[AgentType.TASK] = task_agent
        
        # Agent trả lời
        self.agents[AgentType.RESPONSE] = Agent(
            base_url=self.base_url,
            api_key=self.api_key,
            model=self.model,
            system_prompt="""Bạn là agent trả lời, có nhiệm vụ tạo ra câu trả lời tự nhiên, thân thiện cho người dùng.
            
Bạn sẽ nhận được kết quả từ các agent khác và nhiệm vụ của bạn là:
1. Tổng hợp thông tin từ các agent khác
2. Tạo câu trả lời tự nhiên, dễ hiểu cho người dùng
3. Đảm bảo câu trả lời đầy đủ, chính xác và hữu ích
4. Hãy trả lời câu hỏi dứa dạng đoạn văn, không được gạch đầu dòng. Nếu cần liệt kê các ý thì hãy liệt kê theo dạng đoạn văn.

Hãy sử dụng ngôn ngữ tự nhiên, thân thiện và dễ hiểu."""
        )
        
    async def initialize_all(self):
        """
        Khởi tạo tất cả các agent
        """
        init_tasks = []
        for agent_name, agent in self.agents.items():
            logger.info(f"Initializing agent: {agent_name}")
            init_tasks.append(agent.initialize())
            
        await asyncio.gather(*init_tasks)
        logger.info("All agents initialized successfully")
        
    async def cleanup_all(self):
        """
        Dọn dẹp tất cả các agent
        """
        cleanup_tasks = []
        for agent_name, agent in self.agents.items():
            cleanup_tasks.append(agent.cleanup())
            
        await asyncio.gather(*cleanup_tasks)
        logger.info("All agents cleaned up successfully")
        
    def _build_initial_context(self, transcription: str, device_id: str, request_id: str,
                               max_steps: int = 4, deadline_seconds: float = 25.0) -> Dict[str, Any]:
        """
        Tạo ngữ cảnh tác vụ cho vòng lặp đa-bước.
        """
        now_ts = time.time()
        return {
            "request_id": request_id,
            "device_id": device_id,
            "original_input": transcription,
            "created_at": now_ts,
            "deadline_ts": now_ts + deadline_seconds,
            "max_steps": max_steps,
            "steps": [],  # mỗi phần tử: {step, agent, prompt, result}
            "notes": [],  # ghi chú, giả định
        }

    def _format_context_for_llm(self, context: Dict[str, Any]) -> str:
        """
        Tóm tắt ngữ cảnh cho lời nhắc LLM.
        """
        summary_lines: List[str] = []
        summary_lines.append(f"Yêu cầu gốc: {context.get('original_input','')}")
        if context.get("notes"):
            summary_lines.append("Ghi chú/giả định: " + "; ".join(context["notes"]))
        if context.get("steps"):
            for idx, s in enumerate(context["steps"], 1):
                step = s.get("step", {})
                agent = s.get("agent", "?")
                result_preview = str(s.get("result", ""))
                if len(result_preview) > 400:
                    result_preview = result_preview[:400] + "…"
                summary_lines.append(f"Bước {idx} [{agent}/{step.get('step_type','?')}]: {step.get('goal','')}. KQ: {result_preview}")
        summary = "\n".join(summary_lines)
        logger.info(f"Context summary: {summary}")
        return summary

    async def _plan_next_step(self, context: Dict[str, Any], request_id: str) -> Dict[str, Any]:
        """
        Dùng LLM để lập kế hoạch bước kế tiếp theo schema JSON.
        Trả về dict với khóa: step_type (search|task|answer|clarify), goal, inputs, success_criteria.
        """
        context_summary = self._format_context_for_llm(context)
        try:
            raw = await self._call_agent_chat(
                AgentType.PLANNER,  # tái dụng RESPONSE như planner
                context_summary,
                execute_functions=False,
                request_id=request_id,
                timeout_seconds=12.0,
                retries=0
            )
            
            # Extract JSON from markdown code block if present
            if isinstance(raw, str):
                import re
                # Tìm JSON trong markdown code block
                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw, re.DOTALL)
                if json_match:
                    raw = json_match.group(1)
                step = json.loads(raw)
            else:
                step = {}
                
            if not isinstance(step, dict):
                raise ValueError("Planner output is not a JSON object")
        except Exception as e:
            logger.error(f"[req:{request_id}] Planner error: {e}")
            step = {}

        step_type = str(step.get("step_type", "answer")).lower().strip()
        if step_type not in {"search", "task", "answer", "clarify"}:
            step_type = "answer"
        planned = {
            "step_type": step_type,
            "goal": step.get("goal", context.get("original_input", "")),
            "inputs": step.get("inputs", {}),
            "success_criteria": step.get("success_criteria", []),
        }
        return planned

    async def _execute_step(self, step: Dict[str, Any], context: Dict[str, Any], request_id: str) -> Dict[str, Any]:
        """
        Thực thi bước theo loại: search/task/answer/clarify. Trả về dict kết quả.
        """
        step_type = step.get("step_type")
        goal = step.get("goal", "")
        inputs = step.get("inputs", {})

        context_summary = self._format_context_for_llm(context)

        if step_type == "search" or step_type == "clarify":
            prompt = (
                f"Tìm kiếm thông tin: {goal}. Dựa trên ngữ cảnh sau để chính xác hơn:\n{context_summary}"
            )
            result = await self._call_agent_chat(
                AgentType.SEARCH,
                prompt,
                execute_functions=True,
                request_id=request_id,
                timeout_seconds=20.0,
                retries=1
            )
            agent_used = AgentType.SEARCH
        elif step_type == "task":
            prompt = (
                f"Thực hiện tác vụ: {goal}. Bối cảnh:\n{context_summary}\n"
                f"Đầu vào: {json.dumps(inputs, ensure_ascii=False)}"
            )
            result = await self._call_agent_chat(
                AgentType.TASK,
                prompt,
                execute_functions=True,
                request_id=request_id,
                timeout_seconds=25.0,
                retries=1
            )
            agent_used = AgentType.TASK
        else:  # answer
            prompt = (
                "Tạo câu trả lời cuối cùng cho người dùng, súc tích và chính xác.\n"
                + context_summary
            )
            result = await self._call_agent_chat(
                AgentType.RESPONSE,
                prompt,
                execute_functions=False,
                request_id=request_id,
                timeout_seconds=15.0,
                retries=0
            )
            agent_used = AgentType.RESPONSE

        execution_record = {
            "step": step,
            "agent": agent_used,
            "prompt": prompt,
            "result": result,
        }
        context["steps"].append(execution_record)
        return execution_record

    async def _critique_progress(self, context: Dict[str, Any], request_id: str) -> Dict[str, Any]:
        """
        Dùng critic để quyết định dừng/tiếp tục. Trả về {decision: continue|stop, reason: str}.
        """
        context_summary = self._format_context_for_llm(context)
        critic_prompt = (
            "Bạn là Critic. Đánh giá tiến độ và quyết định 'continue' hoặc 'stop'.\n"
            "Hãy xuất một JSON object: {\"decision\": \"continue|stop\", \"reason\": str}.\n"
            "Nếu đã đủ thông tin cho câu trả lời tốt, hãy 'stop'.\n"
            "Ngữ cảnh:\n" + context_summary
        )
        try:
            raw = await self._call_agent_chat(
                AgentType.RESPONSE,
                critic_prompt,
                execute_functions=False,
                request_id=request_id,
                timeout_seconds=10.0,
                retries=0
            )
            parsed = json.loads(raw) if isinstance(raw, str) else {}
            if not isinstance(parsed, dict):
                raise ValueError("Critic output not JSON object")
        except Exception:
            parsed = {"decision": "stop", "reason": "Critic không hợp lệ, dừng an toàn."}
        decision = str(parsed.get("decision", "stop")).lower()
        if decision not in {"continue", "stop"}:
            decision = "stop"
        return {"decision": decision, "reason": parsed.get("reason", "")}

    def _parse_coordinator_response(self, coordinator_response: str, fallback_request: str) -> (str, str):
        """
        Phân tích phản hồi của coordinator để lấy agent đích và yêu cầu đã làm rõ.

        Ưu tiên định dạng JSON theo schema:
        {"agent": "search|task|response", "request": "..."}

        Nếu không hợp lệ, fallback theo từ khóa, cuối cùng mặc định 'response'.
        """
        allowed_agents = {AgentType.SEARCH, AgentType.TASK, AgentType.RESPONSE}
        target_agent = AgentType.RESPONSE
        clarified_request = fallback_request

        try:
            parsed = json.loads(coordinator_response)
            if isinstance(parsed, dict):
                agent = str(parsed.get("agent", "")).lower().strip()
                request = parsed.get("request", fallback_request)
                if agent in allowed_agents:
                    target_agent = agent
                    clarified_request = request if isinstance(request, str) and request.strip() else fallback_request
                    return target_agent, clarified_request
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

        # Fallback theo từ khóa đơn giản
        try:
            lower_resp = coordinator_response.lower()
            if "search" in lower_resp:
                target_agent = AgentType.SEARCH
            elif "task" in lower_resp:
                target_agent = AgentType.TASK
            else:
                target_agent = AgentType.RESPONSE
        except Exception:
            target_agent = AgentType.RESPONSE

        return target_agent, clarified_request

    async def _route_request(self, transcription: str, request_id: str) -> (str, str):
        """
        Gọi coordinator để xác định agent đích và nội dung yêu cầu đã làm rõ.
        Trả về tuple (target_agent, clarified_request).
        """
        coordinator_response = await self.agents[AgentType.COORDINATOR].chat(
            f"Yêu cầu từ người dùng: {transcription}",
            execute_functions=False
        )

        if not isinstance(coordinator_response, str):
            logger.error(f"[req:{request_id}] Unexpected coordinator response type: {type(coordinator_response)}")
            return AgentType.RESPONSE, transcription

        target_agent, clarified_request = self._parse_coordinator_response(coordinator_response, transcription)
        logger.info(f"[req:{request_id}] Coordinator selected agent: {target_agent}")
        return target_agent, clarified_request

    async def _call_agent_chat(self, agent_type: str, prompt: str, execute_functions: bool, request_id: str,
                               timeout_seconds: float = 15.0, retries: int = 1) -> str:
        """
        Gọi agent.chat với timeout và retry đơn giản (exponential backoff: 0.5, 1.0, 2.0s...).
        """
        last_error: Optional[Exception] = None
        for attempt in range(retries + 1):
            try:
                logger.info(f"[req:{request_id}] Calling agent '{agent_type}' (attempt {attempt + 1}/{retries + 1})")
                return await asyncio.wait_for(
                    self.agents[agent_type].chat(prompt, execute_functions=execute_functions),
                    timeout=timeout_seconds
                )
            except asyncio.TimeoutError as e:
                last_error = e
                logger.warning(f"[req:{request_id}] Agent '{agent_type}' timed out after {timeout_seconds}s (attempt {attempt + 1})")
            except Exception as e:
                last_error = e
                logger.error(f"[req:{request_id}] Agent '{agent_type}' error on attempt {attempt + 1}: {e}")

            if attempt < retries:
                backoff = 0.5 * (2 ** attempt)
                await asyncio.sleep(backoff)

        logger.error(f"[req:{request_id}] Agent '{agent_type}' failed after {retries + 1} attempts: {last_error}")
        raise last_error if last_error else RuntimeError(f"Agent '{agent_type}' failed without specific error")

    async def process_audio_request(self, transcription: str, device_id: str) -> AsyncGenerator[str, None]:
        """
        Xử lý yêu cầu từ audio đã được chuyển đổi thành văn bản
        
        Args:
            transcription: Văn bản được chuyển đổi từ audio
            device_id: ID của thiết bị gửi yêu cầu
            
        Returns:
            str: Câu trả lời cho yêu cầu
        """
        try:
            request_id = str(uuid.uuid4())
            logger.info(f"[req:{request_id}] Processing request from device {device_id}: '{transcription}'")

            # Vòng lặp đa-bước: planner → worker → critic
            context = self._build_initial_context(transcription, device_id, request_id,
                                                  max_steps=4, deadline_seconds=25.0)

            step_index = 0
            while True:
                # Ngân sách thời gian/bước
                if time.time() >= context["deadline_ts"]:
                    logger.warning(f"[req:{request_id}] Deadline reached, stopping and finalizing answer")
                    break
                if step_index >= context["max_steps"]:
                    logger.info(f"[req:{request_id}] Max steps reached: {context['max_steps']}")
                    break

                # Planner: đề xuất bước tiếp theo
                planned_step = await self._plan_next_step(context, request_id)
                logger.debug(f"[req:{request_id}] Planned step: \n{pformat(planned_step)}")
                if planned_step.get("step_type") == "answer":
                    # Tạo câu trả lời cuối cùng trực tiếp
                    execution = await self._execute_step(planned_step, context, request_id)
                    final_response = execution.get("result", "")
                    logger.info(f"[req:{request_id}] Final response for device {device_id}: '{final_response}'")
                    # Yield một lần và kết thúc generator để tránh lặp lại
                    yield final_response
                    return

                # Worker: thực thi bước
                await self._execute_step(planned_step, context, request_id)

                # Critic: quyết định dừng/tiếp tục
                critique = await self._critique_progress(context, request_id)
                if critique.get("decision") == "stop":
                    break

                step_index += 1

            # Tổng hợp câu trả lời cuối cùng từ toàn bộ ngữ cảnh
            final_summary_prompt = (
                "Tạo câu trả lời cuối cùng cho người dùng dựa trên toàn bộ kết quả đã có.\n"
                + self._format_context_for_llm(context)
            )
            final_response = ""
            async for chunk in self.agents[AgentType.RESPONSE].chat_stream(final_summary_prompt):
                if chunk:
                    final_response += chunk
                    yield chunk
            return

        except Exception as e:
            logger.error(f"Error processing audio request: {e}")
            import traceback
            logger.error(traceback.format_exc())
            yield "Xin lỗi, đã xảy ra lỗi khi xử lý yêu cầu của bạn."



    async def __aenter__(self):
        """
        Context manager entry
        """
        await self.initialize_all()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Context manager exit
        """
        await self.cleanup_all()

multi_agent_system = MultiAgentSystem()
if __name__ == "__main__":
    async def test():
           
        # Test các loại yêu cầu khác nhau
        requests = [
            # "Hãy trả lời cho tôi biết làm sao để nấu món phở?",
            # "Tìm kiếm thông tin về thời tiết hôm nay ở Đà Nẵng",
            # "Bật đèn phòng khách giúp tôi",
            # "Tôi muốn biết thông tin về chuyến bay VN123"
            "Thời tiết hôm nay ở Đà Nẵng hôm nay thế nào?"
        ]
        
        for req in requests:
            print(f"\n\n--- Xử lý yêu cầu: {req} ---")
            response = await multi_agent_system.process_audio_request(req, "test_device")
            await generate_tts(response)
            
        await multi_agent_system.cleanup_all()
    
    asyncio.run(test())