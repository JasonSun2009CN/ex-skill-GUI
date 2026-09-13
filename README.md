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

需要 Python 3.10+；macOS 上建议使用 Python 3.11。

```bash
cd ~/Developer/ex-skill-GUI
/usr/local/bin/python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt   # PySide6==6.8.2
python launch.py
```

> `launch.py` 会检查自己是否跑在项目 `.venv` 里：如果用的是别的解释器（系统
> python、IDE 选错、或终端里残留着旧路径的 `(.venv)` 激活），它会自动改用
> `.venv/bin/python` 重新执行，并顺手修正被污染的 `VIRTUAL_ENV` / `PATH`。
> 因此也可以用这条**不依赖 activate**的写法，最不容易出错：
>
> ```bash
> ./.venv/bin/python launch.py
> ```

首次使用：点左上「设置」→ 选服务预设 / 填 API Key 与模型名 →「测试连接」→ 保存。

支持的接口形态（设置里选一种）：

| 形态 | 说明 | 举例 |
|---|---|---|
| OpenAI 兼容 | 填 Base URL + 模型名 | DeepSeek、月之暗面 Moonshot、阿里云百炼 Qwen、智谱 GLM、OpenRouter、OpenAI |
| Anthropic | `/v1/messages` | Claude |

## 界面

- **Apple / macOS 原生风格**：浅色 + 暗色两套主题，可在「设置 → 主题」里选「跟随系统 / 浅色 / 暗色」。
- **左侧角色栏**：可拖拽调整宽度（200–400px）；每个角色显示圆形头像（默认取名字首字生成彩色头像）。右键角色可**更换/移除头像**、删除角色。
- **聊天区**：对方与自己的消息带头像、昵称与完整时间戳；气泡采用微信式绿（自己）/ 白（对方）。
- **多行输入框**：Enter 发送，Shift+Enter 换行，最多自动撑高到 5 行。
- **新建角色向导**：分三步（基本信息 → 导入记录 → 预览与创建）；生成画像时主窗口左侧底部会出现独立的进度面板。

## 使用

1. 点左侧「＋」新建角色，进入向导。
2. **第 1 步**：填显示名、关系类别（恋人/家人需再选性别或成员）、**对方在记录里的名字**（必须与导出文件里一致）、我的昵称（可留空，自动识别为另一方）；可直接上传头像。
3. **第 2 步**：「添加聊天记录文件」导入 `.txt/.md/.log`；可多选，多文件会拼接。
4. **第 3 步**：点「解析预览」确认识别到的说话人；若检测到第三方（群聊/系统消息）会提示将被忽略。
5. 点「创建并生成画像」，左侧底部进度面板会显示生成日志；完成后自动进入对话。
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
    ├── theme.py          主题（浅/暗配色、头像配色、全局样式、跟随系统检测）
    ├── avatar.py         圆形头像组件（首字彩色 / 自定义图片）
    ├── widgets.py        气泡、聊天视图、多行输入框
    ├── main_window.py    可拖拽侧边栏 + 角色列表 + 聊天区 + 生成进度面板
    ├── role_dialog.py    新建角色三步向导
    ├── settings_dialog.py 模型与主题设置
    ├── qtgate.py         Qt 启动预检 + macOS 隐藏标志清理
    └── workers.py        后台线程封装
smoke_test.py             无头测试
```

## Qt 无法启动（qt.qpa.plugin）排查

启动时若看到：

```
qt.qpa.plugin: Could not find the Qt platform plugin "cocoa" in ""
This application failed to start ...
```

### 最常见原因：插件文件被 macOS 标记为「隐藏」（UF_HIDDEN）

Qt 用 `QDir` 默认过滤扫描插件目录，而 `QDir` **默认跳过隐藏文件**。如果
`PySide6/Qt/plugins/` 下的 `.dylib` 被打上了 macOS 的 `hidden` 标志，Qt 就
会认为「找不到平台插件」并直接 abort。

这时**重装 PySide6 也治不好**，因为文件解压后可能立刻又被重新标记。常见触发源：

- 项目放在**百度网盘 / iCloud 等同步目录**下（例如 `~/Documents`），同步客户端会
  把文件标记为隐藏。可用 `ls -la ~/Documents` 看到 `$RECYCLE.BIN`、`desktop.ini`
  之类的同步残留来判断。

**修复**（在项目根目录执行）：

```bash
chflags -R nohidden .venv/lib/python3.11/site-packages/PySide6
```

应用每次启动时也会**自动清理一次**插件目录的隐藏标志（见 `app/ui/qtgate.py` 的
`clear_hidden_plugin_flags`），所以通常直接 `python launch.py` 即可。

> 建议（治本）：把项目移出同步目录，或让同步工具**排除 `.venv/`**。
> 本项目现已迁移到 **`~/Developer/ex-skill-GUI`**，已脱离百度网盘同步目录，
> 隐藏标志不会再被重新加上（可用上面的 `chflags` 命令应急）。

### 其它排查

1. **用系统终端（Terminal.app），而不是 IDE 内置终端 / Run 按钮**运行：
   ```bash
   cd ex-skill-GUI
   source .venv/bin/activate
   python launch.py
   ```
   若只在 IDE 里报错、系统终端正常，通常是 IDE 在 macOS 上的沙箱导致的。
2. **项目迁移过位置、`python: command not found`**：终端里激活的还是**旧路径**的
   venv。表现为提示符仍显示 `(.venv)`，但 PATH 指向已不存在的旧目录 —— 这个
   `(.venv)` 是 `$VIRTUAL_ENV` 的残留显示，具有欺骗性。重开终端即可；或直接
   `./.venv/bin/python launch.py` 绕开 activate。
   用下面这条确认 PATH 里有没有失效条目：
   ```bash
   echo $PATH | tr ':' '\n' | grep -c '\.venv/bin'
   ```
   `launch.py` 现在也会自动清掉这类残留（见其中 `_clean_path`）。
3. 确认隐藏标志是否为 0：
   ```bash
   find .venv/lib/python3.11/site-packages/PySide6/Qt/plugins -flags +hidden | wc -l
   ```
   不为 0 就执行上面的 `chflags` 命令。
4. 仍失败请提供 `python launch.py` 的完整输出与 `python3 -c "import sys; print(sys.executable)"` 的结果。

## 隐私与合规

- 数据默认保存在 `~/.ex-skill`（可用环境变量 `EX_SKILL_DATA_DIR` 覆盖，便于测试/便携）。
- 仅在你发起「生成画像 / 发送消息」时把记录片段发送给你配置的模型服务。
- 请勿上传他人未经同意的隐私记录；使用真实人物资料请获得对方许可。
