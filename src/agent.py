"""
Agent 核心逻辑 - 实现 ReAct 模式和 Memory 机制
"""

import json
import os
import re
from typing import List, Dict, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime

from src.searcher import CodeSearcher


@dataclass
class Memory:
    """记忆结构"""
    file_path: str
    overview: str = ""
    key_definitions: List[str] = field(default_factory=list)
    core_logic: str = ""
    dependencies: List[str] = field(default_factory=list)
    needed_info: str = ""

    def to_dict(self) -> Dict:
        return {
            "file": self.file_path,
            "overview": self.overview,
            "key_definitions": self.key_definitions,
            "core_logic": self.core_logic,
            "dependencies": self.dependencies,
            "needed_info": self.needed_info
        }

    def to_string(self) -> str:
        parts = [f"📄 {self.file_path}"]
        if self.overview:
            parts.append(f"概述: {self.overview}")
        if self.key_definitions:
            parts.append(f"关键定义: {'; '.join(self.key_definitions)}")
        if self.core_logic:
            parts.append(f"核心逻辑: {self.core_logic}")
        if self.dependencies:
            parts.append(f"依赖: {' -> '.join(self.dependencies)}")
        if self.needed_info:
            parts.append(f"待验证: {self.needed_info}")
        return "\n".join(parts)


class ToolExecutor:
    """工具执行器"""

    def __init__(self, searcher: CodeSearcher):
        self.searcher = searcher
        self._tool_registry: Dict[str, Callable] = {}

    def register_tools(self):
        """注册可用工具"""
        self._tool_registry = {
            "read_file": self._read_file,
            "find_files": self._find_files,
            "search_code": self._search_code,
            "find_by_ext": self._find_by_ext,
            "list_dir": self._list_dir,
            "get_file_info": self._get_file_info,
        }

    def execute_tool(self, tool_name: str, **kwargs) -> Dict:
        """执行工具"""
        if tool_name not in self._tool_registry:
            return {"error": f"未知工具: {tool_name}"}

        try:
            result = self._tool_registry[tool_name](**kwargs)
            return {"success": True, "tool": tool_name, "result": result}
        except Exception as e:
            return {"success": False, "tool": tool_name, "error": str(e)}

    def _read_file(self, path: str, max_lines: int = 500, start_line: int = 1) -> Dict:
        return self.searcher.read_file(path, max_lines, start_line)

    def _find_files(self, pattern: str = "*", max_results: int = 20) -> List[str]:
        return self.searcher.find_files(pattern, max_results)

    def _search_code(self, keyword: str, extensions: str = "*", max_results: int = 20) -> List[Dict]:
        return self.searcher.search_code(keyword, extensions, max_results)

    def _find_by_ext(self, extensions: str = "py", max_results: int = 20) -> List[str]:
        return self.searcher.find_by_ext(extensions, max_results)

    def _list_dir(self, path: str = ".") -> Dict:
        return self.searcher.list_dir(path)

    def _get_file_info(self, path: str) -> Dict:
        return self.searcher.get_file_info(path)

    def get_available_tools(self) -> List[Dict]:
        """获取可用工具列表"""
        return [
            {
                "name": "read_file",
                "description": "读取文件内容",
                "params": {
                    "path": {"type": "string", "description": "文件路径"},
                    "max_lines": {"type": "integer", "description": "最大行数", "default": 500},
                    "start_line": {"type": "integer", "description": "起始行号", "default": 1}
                }
            },
            {
                "name": "find_files",
                "description": "按文件名模式查找文件",
                "params": {
                    "pattern": {"type": "string", "description": "文件名模式，如 *.py"},
                    "max_results": {"type": "integer", "description": "最大结果数", "default": 20}
                }
            },
            {
                "name": "search_code",
                "description": "搜索代码内容",
                "params": {
                    "keyword": {"type": "string", "description": "搜索关键词"},
                    "extensions": {"type": "string", "description": "文件扩展名", "default": "*"},
                    "max_results": {"type": "integer", "description": "最大结果数", "default": 20}
                }
            },
            {
                "name": "find_by_ext",
                "description": "按扩展名查找文件",
                "params": {
                    "extensions": {"type": "string", "description": "扩展名，如 py,js"},
                    "max_results": {"type": "integer", "description": "最大结果数", "default": 20}
                }
            },
            {
                "name": "list_dir",
                "description": "列出目录内容",
                "params": {
                    "path": {"type": "string", "description": "目录路径", "default": "."}
                }
            },
            {
                "name": "get_file_info",
                "description": "获取文件信息",
                "params": {
                    "path": {"type": "string", "description": "文件路径"}
                }
            }
        ]


class ReadAgent:
    """Read Agent 主类"""

    def __init__(
        self,
        code_dir: str = ".",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = "gpt-4",
        max_steps: int = 10,
        stream_output: bool = True
    ):
        self.searcher = CodeSearcher(code_dir)
        self.tool_executor = ToolExecutor(self.searcher)
        self.tool_executor.register_tools()

        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4")
        self.max_steps = max_steps
        self.stream_output = stream_output

        self.conversation_history: List[Dict] = []
        self.memories: List[Memory] = []
        self.steps: List[Dict] = []

    def _extract_thought_action(self, response: str) -> tuple:
        """从响应中提取 Thought 和 Action"""
        thought = ""
        action = ""
        action_args = {}

        # 提取 Thought
        thought_match = re.search(r"Thought:\s*(.+?)(?:\nAction:|$)", response, re.DOTALL)
        if thought_match:
            thought = thought_match.group(1).strip()

        # 提取 Action
        action_match = re.search(r"Action:\s*(\w+)\(([^)]*)\)", response)
        if action_match:
            action = action_match.group(1)
            args_str = action_match.group(2)

            # 解析参数
            args_pattern = r'(\w+)="([^"]*)"'
            for match in re.finditer(args_pattern, args_str):
                action_args[match.group(1)] = match.group(2)

        return thought, action, action_args

    def _extract_final_answer(self, response: str) -> tuple:
        """提取最终答案和 Memory"""
        answer = ""
        memory_data = None

        # 提取 Final Answer
        answer_match = re.search(r"Final Answer:\s*(.+?)(?:\nMemory:|$)", response, re.DOTALL)
        if answer_match:
            answer = answer_match.group(1).strip()

        # 提取 Memory
        memory_match = re.search(
            r"Memory:\s*file:\s*(.+?)\noverview:\s*(.+?)\nkey_definitions:\s*(.+?)\ncore_logic:\s*(.+?)\ndependencies:\s*(.+?)\nneeded_info:\s*(.+?)(?:\n\n|$)",
            response,
            re.DOTALL
        )
        if memory_match:
            memory_data = {
                "file": memory_match.group(1).strip(),
                "overview": memory_match.group(2).strip(),
                "key_definitions": [k.strip() for k in memory_match.group(3).split(",") if k.strip()],
                "core_logic": memory_match.group(4).strip(),
                "dependencies": [d.strip() for d in memory_match.group(5).split(",") if d.strip()],
                "needed_info": memory_match.group(6).strip()
            }

        return answer, memory_data

    def _call_llm(self, messages: List[Dict], max_tokens: int = 4000) -> str:
        """调用 LLM API（支持流式输出）"""
        import urllib.request
        import urllib.error

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        data = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.7,
            "stream": True  # 启用流式输出
        }

        full_content = ""
        try:
            req = urllib.request.Request(
                f"{self.base_url}/chat/completions",
                headers=headers,
                data=json.dumps(data).encode("utf-8"),
                method="POST"
            )

            with urllib.request.urlopen(req, timeout=60) as response:
                for line in response:
                    line = line.decode("utf-8").strip()
                    if not line.startswith("data: "):
                        continue
                    if line == "data: [DONE]":
                        break

                    data_str = line[6:]  # 移除 "data: " 前缀
                    try:
                        chunk = json.loads(data_str)
                        if chunk.get("choices") and len(chunk["choices"]) > 0:
                            delta = chunk["choices"][0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                # 流式输出思考内容
                                if self.stream_output:
                                    print(content, end="", flush=True)
                                full_content += content
                    except json.JSONDecodeError:
                        continue

            # 流式输出完成后换行
            if self.stream_output:
                print()

            return full_content

        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else ""
            raise Exception(f"API 错误: {e.code} - {error_body}")
        except Exception as e:
            raise Exception(f"请求错误: {str(e)}")

    def _build_system_prompt(self) -> str:
        """构建系统提示词"""
        tools_info = json.dumps(self.tool_executor.get_available_tools(), ensure_ascii=False, indent=2)

        memories_info = ""
        if self.memories:
            memories_info = "\n\n已读取文件的 Memory:\n" + "\n".join(
                [m.to_string() for m in self.memories]
            )

        return f"""你是一个专业的代码阅读助手，帮助用户理解代码库。

## 工作流程
1. 分析用户问题
2. 思考需要的工具
3. 执行工具调用
4. 观察结果
5. 如果读取了文件，请在 Final Answer 中生成该文件的 Memory
6. 后续步骤使用 Memory 替代原文，避免上下文膨胀

## 可用工具
{tools_info}

## 重要规则
- 只在当前步骤使用读取的文件原文进行分析
- 分析完成后在 Final Answer 中生成 Memory（包含文件概述、关键定义、核心逻辑、依赖关系、待验证信息）
- 不要额外调用 LLM 提取 Memory
- 后续步骤使用 Memory 替代原文
- 最多使用 {self.max_steps} 步完成一个问题
- 始终用中文回答{memories_info}"""

    def _format_step(self, step: Dict) -> str:
        """格式化步骤显示"""
        parts = [f"\n🔄 步骤 {step['step']}"]

        if step.get("thought"):
            parts.append(f"💭 思考: {step['thought']}")

        if step.get("action"):
            parts.append(f"🔧 行动: {step['action']}")

        if step.get("observation"):
            obs = step['observation']
            if isinstance(obs, dict):
                if obs.get("success"):
                    parts.append(f"✅ 结果: {json.dumps(obs.get('result'), ensure_ascii=False, indent=2)[:500]}")
                else:
                    parts.append(f"❌ 错误: {obs.get('error')}")
            else:
                parts.append(f"📋 结果: {str(obs)[:500]}")

        return "\n".join(parts)

    def _think_and_act(self, user_question: str) -> str:
        """思考并执行行动"""
        # 构建消息
        messages = [
            {"role": "system", "content": self._build_system_prompt()}
        ]

        # 添加对话历史
        for msg in self.conversation_history:
            messages.append(msg)

        # 添加当前问题
        messages.append({
            "role": "user",
            "content": f"""{user_question}

请按照以下格式回复：
Thought: 你对这个问题的思考
Action: 工具名(参数="值")

如果可以回答问题，请用：
Thought: 已有足够信息回答
Final Answer: 你的回答

如果读取了文件，请在 Final Answer 末尾添加 Memory，格式如下：
Memory:
file: 文件名
overview: 文件概述（一句话说这个文件是做什么的）
key_definitions: 关键函数/类定义列表（逗号分隔）
core_logic: 核心业务逻辑简述
dependencies: 依赖的其他模块/文件
needed_info: 还需要了解什么信息

示例：
Final Answer: 用户认证通过 JWT 实现...
Memory:
file: auth.py
overview: 处理用户认证逻辑
key_definitions: login(), logout(), JWTValidator
core_logic: 通过 JWT token 验证用户身份
dependencies: user.py, utils/token.py
needed_info:"""
        })

        return self._call_llm(messages, max_tokens=2000)

    def ask(self, question: str) -> str:
        """
        询问关于代码库的问题

        Args:
            question: 用户问题

        Returns:
            Agent 的回答
        """
        self.steps = []
        self.conversation_history.append({"role": "user", "content": question})

        # 流式模式下输出标题
        if self.stream_output:
            print(f"\n{'='*60}")
            print(f"🤔 问题: {question}")
            print(f"\n📝 分析过程:")

        for step in range(1, self.max_steps + 1):
            # 获取思考和行动
            response = self._think_and_act(question)

            # 记录步骤
            step_info = {"step": step, "raw_response": response}
            thought, action, action_args = self._extract_thought_action(response)
            step_info["thought"] = thought
            step_info["action_str"] = f"{action}({action_args})" if action else ""

            # 检查是否有最终答案和 Memory
            final_answer, memory_data = self._extract_final_answer(response)

            # 如果有 Memory，保存到列表
            if memory_data:
                path = memory_data.get("file", "")
                if path:
                    # 检查是否已存在
                    existing = [m for m in self.memories if m.file_path == path]
                    if existing:
                        self.memories.remove(existing[0])
                    # 创建新的 Memory 对象
                    memory = Memory(
                        file_path=path,
                        overview=memory_data.get("overview", ""),
                        key_definitions=memory_data.get("key_definitions", []),
                        core_logic=memory_data.get("core_logic", ""),
                        dependencies=memory_data.get("dependencies", []),
                        needed_info=memory_data.get("needed_info", "")
                    )
                    self.memories.append(memory)

            if final_answer:
                step_info["final_answer"] = final_answer
                self.steps.append(step_info)
                self.conversation_history.append({"role": "assistant", "content": final_answer})

                # 流式输出最终答案
                if self.stream_output:
                    print(f"\n{'='*60}")
                    print(f"💡 回答:\n{final_answer}")
                    return ""
                else:
                    return self._format_output(question, final_answer)

            # 执行工具调用
            if action:
                step_info["action"] = f"{action}({action_args})"
                tool_result = self.tool_executor.execute_tool(action, **action_args)
                step_info["observation"] = tool_result

                # 流式输出当前步骤
                if self.stream_output:
                    print(self._format_step(step_info))

                # 将观察结果添加到对话
                self.conversation_history.append({
                    "role": "user",
                    "content": f"Observation: {json.dumps(tool_result, ensure_ascii=False)}"
                })

            self.steps.append(step_info)

        # 超时，返回最后的结果
        if self.stream_output:
            print(f"\n{'='*60}")
            print(f"💡 回答:\n已达到最大步骤数限制，请尝试更具体的问题。")
            return ""
        else:
            return self._format_output(question, "已达到最大步骤数限制，请尝试更具体的问题。")

    def _format_output(self, question: str, answer: str) -> str:
        """格式化输出"""
        output = [f"\n{'='*60}"]
        output.append(f"🤔 问题: {question}")
        output.append(f"\n📝 分析过程:")

        for step_info in self.steps:
            output.append(self._format_step(step_info))

        output.append(f"\n{'='*60}")
        output.append(f"💡 回答:\n{answer}")

        return "\n".join(output)

    def clear_memory(self):
        """清空 Memory"""
        self.memories = []

    def clear_history(self):
        """清空对话历史"""
        self.conversation_history = []
        self.memories = []
        self.steps = []

    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            "conversation_length": len(self.conversation_history),
            "memory_count": len(self.memories),
            "total_steps": len(self.steps),
            "code_dir": str(self.searcher.root_dir)
        }
