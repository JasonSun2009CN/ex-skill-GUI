# ex-skill

> 语言 / Language: [English](README.md)

一个本地桌面应用：将聊天记录等感情证据整理为人格画像，并生成可复用的模仿对话 skill。

## 功能

- 通过桌面 GUI 导入 `.txt`、`.md` 或 `.log` 聊天记录。
- 设置用户和分析对象的别名，预览解析后的对话回合。
- 支持 OrcaRouter、OpenRouter、OpenAI、Anthropic、Gemini、DeepSeek、百炼/Qwen、Kimi、GLM、Groq、Mistral、Together、硅基流动和其他 OpenAI 兼容服务。
- 支持前任、伴侣、暧昧对象、朋友、细分家庭成员、同事和自定义关系，并将关系边界用于分析和对话。
- 校验生成的人格画像，并生成自包含的模仿 skill。
- 加载生成的 skill 进行对话；证据和生成文件默认保存在本地。

## 环境要求

- Python 3.10 或更高版本
- macOS、Linux 或 Windows
- 一个受支持服务商的 API Key

安装依赖：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows 激活虚拟环境请使用 `.venv\Scripts\activate`。

## 启动

```bash
python3 launch.py
```

## GUI 使用流程

1. 打开「设置」，选择服务商，填写 API Key、Base URL 和模型。OrcaRouter 位于列表第一项；它的 API 地址需要按你的账户文档填写。
2. 打开「资料」，添加聊天记录并填写用户和对象别名。
3. 预览解析结果并确认资料。
4. 在「准备」中生成画像和模仿 skill，也可以直接使用一键准备流程。
5. 在「对话」中加载生成的 skill 并开始聊天。

配置文件通常保存到 `~/.ex-skill/config.json`。证据保存在 `evidence/`，生成的画像和 skill 保存在 `generated/`。

## 目录结构

```text
app/                              Python 应用代码
app/core/                         解析、分析、生成、校验和大模型服务商
app/ui/                           PySide6 桌面界面
personality-analysis-skill/       分析提示词、评分标准和画像模板
imitation-skill-generator/       模仿 skill 模板和校验报告
evidence/                         本地输入证据；除 .gitkeep 外被忽略
generated/                        本地画像和 skill；被 Git 忽略
smoke_test.py                     低依赖引擎冒烟测试
requirements.txt                  运行时依赖
launch.py                         唯一 GUI 启动脚本
```

## 校验

运行内置冒烟测试和语法检查：

```bash
python3 smoke_test.py
python3 -m compileall -q app smoke_test.py
```

冒烟测试覆盖聊天记录解析、画像校验、对象摘要提取和模仿 skill 生成。

## 隐私说明

GUI 会将证据和生成结果写入本地，但执行分析或对话时会调用「设置」中配置的大模型服务。不要提交私人聊天记录、生成的画像、API Key 或其他敏感信息。请仅在获得适当同意的情况下使用模仿功能，并将人格分析视为一种解读，而不是诊断。
