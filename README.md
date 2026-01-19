# Read Agent

纯 Python 标准库实现的代码阅读智能助手。

## 特性

- **零依赖** - 只用 Python 标准库，无任何第三方包
- **多轮对话** - 支持持续追问，上下文记忆
- **智能搜索** - 支持文件名搜索、代码搜索、扩展名搜索
- **自然语言问答** - 用中文提问，快速理解代码
- **并行工具调用** - 同时执行多个工具，效率更高
- **Memory 机制** - 智能压缩上下文，避免上下文膨胀
```

## 技术特性

### 1. ReAct 模式

采用 ReAct（Reasoning + Acting）模式，通过思考-行动-思考的循环来理解代码：

```
Thought: 我需要先了解项目结构
Action: find_files(pattern="*.py")
Observation: 找到 10 个 Python 文件

Thought: 用户关心认证逻辑
Action: search_code(keyword="auth", extensions="py")
Observation: 在 auth.py 找到相关代码

Final Answer: 用户认证通过 JWT 实现...
```

### 2. 并行工具调用

支持同时执行多个工具，显著提升效率：

```python
# 同时读取多个文件
Action: read_file(path="auth.py")
Action: read_file(path="user.py")
Action: search_code(keyword="login")
# 系统并行执行，节省时间
```

### 3. Memory 机制

**解决痛点**：长对话时上下文膨胀问题

- 读取文件后自动提取关键信息（Memory）
- 后续步骤只传递 Memory，不再重复传递原文
- Memory 包含：文件概述、关键定义、核心逻辑、依赖关系、需要的信息
- 上下文节省可达 **90%+**


### 4. 上下文管理

| 场景 | 传统方式 | 本项目 |
|------|---------|--------|
| 读取 5 个文件 | 2500 行原文 | 5 条 Memory (~200行) |
| 读取 10 个文件 | 5000 行原文 | 10 条 Memory (~400行) |
| 上下文节省 | - | **~92%** |

## 安装

无需安装依赖，直接运行即可。

```bash
git clone https://github.com/your/repo.git
cd read-agent
python main.py
```

## 使用方法

### 1. 配置 API Key

```bash
echo "OPENAI_API_KEY=your-api-key" > .env
```


### 2. 指定代码目录

默认读取当前目录，可通过环境变量指定：

```bash
export CODE_DIR="/path/to/your/code"
python main.py
```

或者在 `.env` 文件中配置：
```bash
CODE_DIR=/path/to/your/code
```

### 3. 环境变量配置

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `OPENAI_API_KEY` | OpenAI API Key | 必填 |
| `OPENAI_BASE_URL` | API 基础 URL | `https://api.openai.com/v1` |
| `OPENAI_MODEL` | 模型名称 | `gpt-4` |
| `CODE_DIR` | 代码目录 | `.` |
| `MAX_STEPS` | 最大步骤数 | `10` |

### 4. 开始提问

```
🤔 这个项目是做什么的？
🤔 用户认证是如何实现的？
🤔 找到处理 API 请求的代码
🤔 这个函数的作用是什么？
```

## 命令

- `quit` / `exit` / `q` - 退出
- `clear` - 清空对话历史

## 可用工具

| 工具 | 描述 | 示例 |
|------|------|------|
| `read_file` | 读取文件内容 | `read_file(path="auth.py", max_lines="100")` |
| `find_files` | 按文件名查找 | `find_files(pattern="*.py")` |
| `search_code` | 搜索代码内容 | `search_code(keyword="login", extensions="py")` |
| `find_by_ext` | 按扩展名查找 | `find_by_ext(ext="py")` |

## 工作原理

1. 用户用自然语言提问
2. Agent 分析问题，决定搜索策略
3. 动态搜索相关代码文件
4. **读取到的原始文件内容只用于当次分析**（默认最多 500 行）
5. **Agent 自动将文件内容压缩为 Memory**（关键函数/类、关键逻辑、关系等）
6. 后续步骤只携带 Memory，不再重复携带原文
7. 理解代码并生成回答
8. 保持对话上下文（以 Memory 为主，避免上下文膨胀）

## 配置选项

### 代码搜索限制

`CodeSearcher` 支持以下配置：

```python
searcher = CodeSearcher(
    root_dir="/path/to/code",  # 代码根目录
    max_files=20               # 最大搜索结果数
)
```

### 排除规则

自动排除以下目录和文件：
- 目录：`.git`, `__pycache__`, `node_modules`, `.venv`, `venv`, `dist`, `build`
- 文件：`.pyc`, `.pyo`, `.pyd`, `.so`, `.dll`, `.exe`, `.bin`, `.class`

### 修改提示词

在 [prompts.py](prompts.py) 中修改 `SYSTEM_PROMPT` 和 `MEMORY_SYSTEM_PROMPT`。

