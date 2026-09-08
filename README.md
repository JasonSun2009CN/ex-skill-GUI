# ex-skill 角色聊天

一个**本地桌面聊天应用**：导入你和某个人的聊天记录，让大语言模型生成对方的「人格画像」，然后在窗口里直接和「那个人」聊天。

适用场景：个人关系复盘、沟通风格研究、角色模拟、对话体验实验。

> ⚠️ 说明：生成的角色画像只是基于有限资料的**推断**，不代表心理诊断或对真实人物的绝对定义；请勿用于冒充或欺骗。

## 核心流程

```
新建角色（选关系 + 导入聊天记录）
   ↓  一次 LLM 分析
结构化「人格画像」（存本机 ~/.ex-skill）
   ↓
以该角色身份聊天（历史存本机，可续聊）
```

- 关系类别：**恋人（男/女）**、**家人（父/母/兄/弟/姐/妹）**、**朋友**、**同事**、**其他**
- 画像字段：身份、性格维度、沟通风格、情绪与情感表达、口头禅/用语习惯、回复长度、关系边界
- 所有数据只存本机（默认 `~/.ex-skill`），不打包上传；除发起请求外不联网

## 安装与运行

需要 Python 3.10+。

```bash
cd ex-skill-GUI
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python launch.py
```

首次使用：点左上「设置」→ 选服务预设 / 填 API Key 与模型名 →「测试连接」→ 保存。

支持的接口形态（设置里选一种）：

| 形态 | 说明 | 举例 |
|---|---|---|
| OpenAI 兼容 | 填 Base URL + 模型名 | DeepSeek、阿里云百炼 Qwen、智谱 GLM、OpenRouter、OpenAI |
| Anthropic | `/v1/messages` | Claude |

## 使用

1. 点左侧「＋」新建角色。
2. 填：显示名、关系类别（恋人/家人需再选性别或成员）、**对方在记录里的名字**（必须与导出文件里一致）、我的昵称（可留空，自动识别为另一方）。
3. 「添加聊天记录文件」导入 `.txt/.md/.log`；可多选，多文件会拼接。
4. 点「解析预览」确认识别到的说话人；若检测到第三方（群聊/系统消息）会提示将被忽略。
5. 点「创建并生成画像」，等待进度完成后自动进入对话。
6. 在输入框聊天；Enter 发送。聊天记录会持续保存，下次打开可继续。

### 聊天记录格式

应用能自动解析两种常见写法（也兼容微信/QQ/Tim 导出清洗后的纯文本）：

```
Joanna  23:04          # 格式：名字 + 两个及以上空格 + 时间（可选）
今天的月亮很好看

Joanna  23:05
诶呀 我又开始话痨了

我  23:06              # 或者「我：内容」的行内写法
没有啊 你说
```

- 分析时只保留**你和对方两条线**；其它说话人会被丢弃。
- 记录过长时只取**最近一段**进行分析（近期风格最能代表当下）。

## 测试（无 GUI / 无网络）

```bash
python smoke_test.py      # 引擎层：解析、画像结构、存储往返、假 LLM 的生成/聊天
```

## 目录结构

```
app/
├── main.py               入口（含 Qt 启动预检）
├── core/                引擎（不依赖 Qt，可无头测试）
│   ├── evidence.py       聊天记录解析/说话人识别
│   ├── models.py         关系类别/画像 schema
│   ├── persona_prompts.py  画像分析提示与聊天系统提示
│   ├── persona_analyzer.py 一次 LLM 调用生成画像
│   ├── persona_store.py  本地文件存储
│   ├── pipeline.py       新建角色编排
│   ├── chat_session.py   对话会话（画像→系统提示、历史持久化）
│   └── llm/client.py     统一 LLM 客户端（OpenAI 兼容 / Anthropic）
└── ui/                   PySide6 界面
    ├── main_window.py    左侧角色列表 + 右侧聊天区
    ├── role_dialog.py    新建角色向导
    ├── settings_dialog.py 模型设置
    ├── qtgate.py         Qt 启动预检
    └── workers.py        后台线程封装
smoke_test.py             无头测试
```

## Qt 无法启动（qt.qpa.plugin）排查

启动时若看到：

```
qt.qpa.plugin: Could not find the Qt platform plugin "cocoa" in ""
This application failed to start ...
```

按顺序尝试：

1. **用系统终端（Terminal.app），而不是 IDE 内置终端 / Run 按钮**运行：
   ```bash
   cd ex-skill-GUI
   source .venv/bin/activate
   python launch.py
   ```
   若只在 IDE 里报错、系统终端正常，通常是 IDE 在 macOS 上的沙箱导致的，请用系统终端运行。
2. 在项目 venv 里干净重装 PySide6：
   ```bash
   .venv/bin/pip uninstall -y PySide6 PySide6-Essentials PySide6-Addons shiboken6
   .venv/bin/pip install "PySide6==6.11.2"
   ```
3. 仍失败请提供 `python launch.py` 的完整输出与 `python3 -c "import sys; print(sys.executable)"` 的结果。

## 隐私与合规

- 数据默认保存在 `~/.ex-skill`（可用环境变量 `EX_SKILL_DATA_DIR` 覆盖，便于测试/便携）。
- 仅在你发起「生成画像 / 发送消息」时把记录片段发送给你配置的模型服务。
- 请勿上传他人未经同意的隐私记录；使用真实人物资料请获得对方许可。
