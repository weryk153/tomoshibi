# Tomoshibi

和喜欢的动漫角色聊天、互动的 app。免费、开源，macOS 和 Windows 都能用。

**语言：** [English](./README.md) | [繁體中文](./README.TW.md) | [日本語](./README.JP.md) | [한국어](./README.KR.md) | 简体中文

![Tomoshibi](assets/tomoshibi-hero.png)

## 能做什么

- 角色会根据对话内容自己做表情和动作，Live2D 和 VRM（3D）模型都可以。
- 角色说什么语言可以自己设置。声音的语言不一样时，会先翻译再念。
- 会记得你聊过的事，你一阵子没说话，它也会主动找你聊。
- 可以直接用说的，说到一半也能打断它。
- 放进自己的模型、写好人设，就是你的角色。

## 安装

到 [Releases](https://github.com/weryk153/tomoshibi/releases/latest) 下载：

| 电脑 | 文件 |
|---|---|
| Apple Silicon Mac（M1 以后） | `arm64.dmg` |
| Intel Mac | `x64.dmg` |
| Windows 10／11 | `setup.exe` |

打开之后跟着设置向导走：

1. 接上 AI。点「一键安装」会装好免费的 [Ollama](https://ollama.com) 和本地模型，不用账号，对话也不会离开你的电脑。也可以粘贴 OpenAI、Claude 或 Gemini 的 API key。
2. 选 2D 或 3D 角色。
3. 要不要装本地语音 GPT-SoVITS，也可以之后再决定。

第一次打开会下载 Python 和语音识别模型，大约 1.5GB，之后就不用等了。

app 没有签名，第一次打开会被系统拦下：

- macOS：先点「完成」，再到「系统设置 → 隐私与安全性」点「仍要打开」。
- Windows：在蓝色窗口点「更多信息 → 仍要运行」。

### 从源码运行

需要 Python 3.10～3.12 和 [uv](https://github.com/astral-sh/uv)。

```bash
git clone https://github.com/weryk153/tomoshibi.git && cd tomoshibi
uv run run_server.py
```

然后打开 http://localhost:12393。

不想用终端的话，也可以下载 ZIP 解压，双击 `start-companion.command`（macOS）或 `start-companion.bat`（Windows）。弹出来的那个窗口就是服务器，聊天时不要关。

## 放自己的角色

把模型文件夹放进 `live2d-models/` 或 `vrm-models/`，到「设置 → 角色」编辑角色，就能选到它。人设、回复语言、参考音也在同一页。

详细做法：[Live2D](docs/add-live2d-character.md)、[VRM](docs/add-vrm-character.md)。

内置的模型只放了授权允许分发的：Live2D 官方示例（mao_pro、haru、hiyori）和 CC0 的 VRM 角色「篠」。请不要把有版权的角色、图或声音放进这个仓库。

## AI 模型

「一键安装」用的是 Ollama 的 `qwen2.5:3b`，一般 8～16GB 内存的电脑就跑得动。想要回复更聪明，可以在「设置 → 语言模型」换更大的模型，或改用 API key。

免费的 API 也能用，选「自定义端点（高级）」填 base URL：

- Gemini：`https://generativelanguage.googleapis.com/v1beta/openai/`
- Groq：`https://api.groq.com/openai/v1`
- Cerebras：`https://api.cerebras.ai/v1`

请选普通的对话模型。思考型（reasoning）模型会把回答放在另一个字段，app 读不到，界面会是空白，也没有声音。一定要用的话，在 `conf.yaml` 的 LLM 设置里加上：

```yaml
extra_body:
  reasoning_effort: 'none'
```

## 语音

默认用免费的 edge-tts，需要联网。

想要更自然、在自己电脑上跑的声音，可以在向导或「设置 → 语音合成」一键安装 [GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS)。支持 Apple Silicon Mac（下载约 3.8GB）和 Windows（约 8.2GB）。默认声音来自 つくよみちゃんコーパス（CV.夢前黎）。

它装在 `~/Library/Application Support/Tomoshibi/GPT-SoVITS`（macOS）或 `%LOCALAPPDATA%\Tomoshibi\GPT-SoVITS`（Windows），不要了就删掉那个文件夹。已经自己搭好 GPT-SoVITS 的话，看[这篇](docs/custom-voice-gpt-sovits.md)。

拿真人的声音当参考音，法律责任要自己承担。

## 常见问题

**有文字但没有声音**
用 GPT-SoVITS 的话，打开后它要大约一分钟加载。还是没声音，就到「设置 → 语音合成」换回 Edge TTS。

**角色都不回话**
还没接上 AI，到「设置 → 语言模型」设置。用 Ollama 的话，确认 Ollama app 正在运行。

**打不开，或窗口一开就关**
先更新到最新版。还是不行，打开 `conf.yaml`，把 `asr_model: 'faster_whisper'` 改成 `asr_model: 'sherpa_onnx_asr'`。

## 其他文档

- [用手机或平板连接（Tailscale）](docs/remote-access-tailscale.md)
- [场景](docs/scene-management.md)、[舞台特效](docs/stage-effects.md)、[界面说明](docs/ui-features.md)

## 致谢与许可

Tomoshibi 建立在 [Open-LLM-VTuber](https://github.com/Open-LLM-VTuber/Open-LLM-VTuber) 之上，也请去支持原项目。

- 这个项目自己的代码是 MIT。上游的服务器代码也是 MIT，Copyright (c) 2025 Yi-Ting Chiu。
- `frontend/` 里的网页前端采用 Open-LLM-VTuber License 1.0（Apache-2.0 加上额外条款），商业用途要另外取得授权。
- 内置的 Live2D 示例模型依 Live2D 无偿提供素材许可使用，付费或商用版本必须换掉（见 [`LICENSE-Live2D.md`](./LICENSE-Live2D.md)）：
  > This content uses sample data owned and copyrighted by Live2D Inc.
- 其他组件的许可见 [`NOTICE`](./NOTICE)。

## 反馈

有问题或想法，欢迎开 issue 或 PR。
