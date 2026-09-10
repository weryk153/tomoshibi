# Tomoshibi

좋아하는 애니메이션 캐릭터와 대화하고 교감하는 앱이에요. 무료 오픈소스이고, macOS와 Windows에서 쓸 수 있어요.

**언어:** [English](./README.md) | [繁體中文](./README.TW.md) | [日本語](./README.JP.md) | 한국어 | [简体中文](./README.CN.md)

![Tomoshibi](assets/tomoshibi-hero.png)

## 할 수 있는 것

- 캐릭터가 대화 내용에 맞춰 스스로 표정과 동작을 지어요. Live2D와 VRM(3D) 모델을 모두 지원해요.
- 캐릭터가 말하는 언어를 직접 정할 수 있어요. 목소리 언어가 다르면 번역한 뒤에 읽어 줘요.
- 나눈 이야기를 기억하고, 한동안 말이 없으면 먼저 말을 걸어요.
- 목소리로 말을 걸 수 있고, 캐릭터가 말하는 중간에 끼어들 수도 있어요.
- 내 모델을 넣고 페르소나를 쓰면 나만의 캐릭터가 돼요.

## 설치

[Releases](https://github.com/weryk153/tomoshibi/releases/latest)에서 내려받으세요.

| 컴퓨터 | 파일 |
|---|---|
| Apple 실리콘 Mac(M1 이후) | `arm64.dmg` |
| Intel Mac | `x64.dmg` |
| Windows 10/11 | `setup.exe` |

실행한 뒤 설정 마법사를 따라가면 돼요.

1. AI를 연결해요. "원클릭 설치"를 누르면 무료 [Ollama](https://ollama.com)와 로컬 모델이 설치돼요. 계정이 필요 없고, 대화가 컴퓨터 밖으로 나가지 않아요. OpenAI, Claude, Gemini API 키를 붙여 넣어도 돼요.
2. 2D 또는 3D 캐릭터를 골라요.
3. 로컬 음성 GPT-SoVITS를 설치할지 정해요. 나중에 설치해도 돼요.

처음 실행할 때 Python과 음성 인식 모델(약 1.5GB)을 내려받아요. 다음부터는 기다리지 않아요.

앱에 서명이 없어서 처음 실행할 때 시스템이 막아요.

- macOS: "완료"를 누른 뒤 "시스템 설정 → 개인정보 보호 및 보안"에서 "그래도 열기"를 눌러요.
- Windows: 파란 창에서 "추가 정보 → 실행"을 눌러요.

### 소스에서 실행하기

Python 3.10~3.12와 [uv](https://github.com/astral-sh/uv)가 필요해요.

```bash
git clone https://github.com/weryk153/tomoshibi.git && cd tomoshibi
uv run run_server.py
```

그다음 http://localhost:12393 을 열어요.

터미널을 쓰기 싫다면 ZIP을 내려받아 압축을 풀고 `start-companion.command`(macOS)나 `start-companion.bat`(Windows)를 더블클릭하세요. 열린 창이 서버라서 대화하는 동안 닫으면 안 돼요.

## 내 캐릭터 넣기

모델 폴더를 `live2d-models/`나 `vrm-models/`에 넣고 "설정 → 캐릭터"에서 캐릭터를 편집하면 고를 수 있어요. 페르소나, 답변 언어, 참조 음성도 같은 페이지에 있어요.

자세한 방법: [Live2D](docs/add-live2d-character.md), [VRM](docs/add-vrm-character.md)

기본으로 들어 있는 모델은 배포가 허락된 것뿐이에요. Live2D 공식 샘플(mao_pro, haru, hiyori)과 CC0 VRM 캐릭터 "시노"예요. 저작권이 있는 캐릭터, 그림, 목소리는 이 저장소에 넣지 말아 주세요.

## AI 모델

"원클릭 설치"로 들어가는 모델은 Ollama의 `qwen2.5:3b`이고, 메모리 8~16GB인 보통 노트북에서 돌아가요. 더 똑똑한 답변을 원하면 "설정 → LLM"에서 더 큰 모델로 바꾸거나 API 키를 쓰세요.

무료 API도 쓸 수 있어요. "사용자 지정 엔드포인트(고급)"를 고르고 base URL을 입력하세요.

- Gemini: `https://generativelanguage.googleapis.com/v1beta/openai/`
- Groq: `https://api.groq.com/openai/v1`
- Cerebras: `https://api.cerebras.ai/v1`

일반 대화 모델을 고르세요. 추론(reasoning) 모델은 답을 다른 칸에 넣어서 앱이 읽지 못하고, 답변이 비어 있고 목소리도 안 나와요. 꼭 써야 한다면 `conf.yaml`의 LLM 설정에 아래를 추가하세요.

```yaml
extra_body:
  reasoning_effort: 'none'
```

## 음성

기본은 무료 edge-tts이고, 인터넷 연결이 필요해요.

내 컴퓨터에서 돌아가는 더 자연스러운 목소리를 원하면, 마법사나 "설정 → TTS"에서 [GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS)를 원클릭으로 설치할 수 있어요. Apple 실리콘 Mac(다운로드 약 3.8GB)과 Windows(약 8.2GB)를 지원해요. 기본 목소리는 츠쿠요미짱 코퍼스(CV. 유메사키 레이)예요.

설치 위치는 `~/Library/Application Support/Tomoshibi/GPT-SoVITS`(macOS) 또는 `%LOCALAPPDATA%\Tomoshibi\GPT-SoVITS`(Windows)예요. 필요 없어지면 그 폴더를 지우면 돼요. GPT-SoVITS를 이미 직접 돌리고 있다면 [이 문서](docs/custom-voice-gpt-sovits.md)를 보세요.

실제 사람의 목소리를 참조 음성으로 쓴다면, 그에 대한 법적 책임은 본인에게 있어요.

## 자주 묻는 질문

**글자는 나오는데 목소리가 안 나와요**
GPT-SoVITS는 실행 후 불러오는 데 1분쯤 걸려요. 그래도 안 나오면 "설정 → TTS"에서 Edge TTS로 돌려 놓으세요.

**캐릭터가 대답을 안 해요**
아직 AI가 연결되지 않았어요. "설정 → LLM"에서 설정하세요. Ollama를 쓴다면 Ollama 앱이 실행 중인지 확인하세요.

**앱이 안 열리거나 창이 바로 닫혀요**
먼저 최신 버전으로 업데이트하세요. 그래도 안 되면 `conf.yaml`에서 `asr_model: 'faster_whisper'`를 `asr_model: 'sherpa_onnx_asr'`로 바꾸세요.

## 다른 문서

- [휴대폰이나 태블릿에서 쓰기(Tailscale)](docs/remote-access-tailscale.md)
- [장면](docs/scene-management.md), [무대 효과](docs/stage-effects.md), [화면 설명](docs/ui-features.md)

## 크레딧과 라이선스

Tomoshibi는 [Open-LLM-VTuber](https://github.com/Open-LLM-VTuber/Open-LLM-VTuber)를 바탕으로 만들었어요. 원래 프로젝트도 응원해 주세요.

- 이 프로젝트의 자체 코드는 MIT예요. 업스트림 서버 코드도 MIT예요(Copyright (c) 2025 Yi-Ting Chiu).
- `frontend/`의 웹 프론트엔드는 Open-LLM-VTuber License 1.0(Apache-2.0과 추가 조건)이에요. 상업적으로 쓰려면 별도 라이선스가 필요해요.
- 들어 있는 Live2D 샘플 모델은 Live2D 무상 제공 자료 라이선스에 따라 쓰고 있어요. 유료 버전이나 상업 버전에서는 반드시 바꿔야 해요([`LICENSE-Live2D.md`](./LICENSE-Live2D.md)).
  > This content uses sample data owned and copyrighted by Live2D Inc.
- 다른 구성 요소의 라이선스는 [`NOTICE`](./NOTICE)에 있어요.

## 피드백

질문이나 아이디어는 issue나 PR로 남겨 주세요.
