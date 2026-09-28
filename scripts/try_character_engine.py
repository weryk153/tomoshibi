"""Run the verified engine wheel through Tomoshibi's real text/output pipeline.

This local trial does not replace Tomoshibi's application agent or user history.
Use --interactive for manual turns after the automated checks.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import sys
import time


def arguments():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--tomoshibi', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--model', default='tomoshibi-engine-trial')
    p.add_argument('--interactive', action='store_true')
    return p.parse_args()


async def main(args):
    root = args.tomoshibi.resolve()
    sys.path.insert(0, str(root))
    os.chdir(root)
    import yaml
    from loguru import logger
    logger.remove()
    from ai_character_engine import CharacterProfile, CharacterRuntime, __version__
    from ai_character_engine.llm.local import OpenAICompatibleChatClient
    from ai_character_engine.llm.models import Message
    from ai_character_engine_tomoshibi import TomoshibiBridge, TomoshibiIntegrationConfig
    from src.open_llm_vtuber.agent.input_types import BatchInput, TextData, TextSource
    from src.open_llm_vtuber.agent.output_types import SentenceOutput
    from src.open_llm_vtuber.agent.transformers import (
        sentence_divider, actions_extractor, display_processor, tts_filter,
    )
    from src.open_llm_vtuber.avatar_model import AvatarModel
    from src.open_llm_vtuber.config_manager import TTSPreprocessorConfig
    from src.open_llm_vtuber.conversation_quality import normalize_output_language_variant

    config_path = root / 'conf.yaml'
    before = hashlib.sha256(config_path.read_bytes()).hexdigest()
    conf = yaml.safe_load(config_path.read_text())['character_config']
    avatar = AvatarModel(conf.get('live2d_model_name') or 'mao_pro')
    client = OpenAICompatibleChatClient(
        model=args.model, base_url='http://127.0.0.1:1234/v1',
        backend='lmstudio', timeout_seconds=90,
        request_options={'temperature': 0.1, 'max_tokens': 240,
                         'extra_body': {'reasoning_effort': 'none'}},
    )
    profile = CharacterProfile(
        id='tomoshibi-engine-trial', name=conf.get('character_name') or 'Mao',
        description='你是 Mao，親切的 AI 角色。只用繁體中文簡短回應，一至兩句。'
                '記住使用者在這段對話告訴你的資料。不要杜撰。可使用 [joy] 或 [neutral] 表情標籤。',
    )
    bridges = []
    def new_bridge():
        bridge = TomoshibiBridge(
            CharacterRuntime(character=profile, llm=client, max_history_messages=20),
            config=TomoshibiIntegrationConfig(turn_timeout_seconds=100),
        )
        bridges.append(bridge)
        return bridge

    tts_config = TTSPreprocessorConfig.model_validate(conf['tts_preprocessor_config'])
    records = []
    async def turn(bridge, text):
        batch = BatchInput(texts=[TextData(source=TextSource.INPUT, content=text)])
        queue = asyncio.Queue()
        async def delta(value):
            await queue.put(value)
        async def producer():
            try:
                return await bridge.process('\n'.join(t.content for t in batch.texts), on_text_delta=delta)
            finally:
                await queue.put(None)
        @tts_filter(tts_config)
        @display_processor()
        @actions_extractor(avatar)
        @sentence_divider(faster_first_response=True, segment_method='pysbd', valid_tags=['think'])
        async def outputs():
            while True:
                value = await queue.get()
                if value is None:
                    break
                yield value
            await task  # Never report a partial failed stream as a successful turn.
        task = asyncio.create_task(producer())
        started = time.perf_counter()
        sentences = []
        try:
            async for item in outputs():
                if not isinstance(item, SentenceOutput):
                    raise AssertionError(f'Unexpected host output: {type(item).__name__}')
                sentences.append({
                    'display_text': normalize_output_language_variant(item.display_text.text, '繁體中文'),
                    'tts_text': normalize_output_language_variant(item.tts_text, '繁體中文'),
                    'actions': item.actions.to_dict(),
                })
            result = await task
            bridge.replace_reply(normalize_output_language_variant(result.text, '繁體中文'))
            assert sentences and ''.join(s['display_text'] for s in sentences).strip()
            record = {'input': text, 'sentences': sentences,
                      'elapsed_seconds': round(time.perf_counter() - started, 3),
                      'history_messages': len(bridge.runtime.history),
                      'engine_model': result.response.model}
            records.append(record)
            print('Mao: ' + ''.join(s['display_text'] for s in sentences), flush=True)
            return record
        finally:
            if not task.done():
                task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    checks = {}
    try:
        bridge = new_bridge()
        first = await turn(bridge, '我叫晨星，今天喝的是烏龍茶。請用一句話回應，開頭使用 [joy]。')
        checks['real_model_to_host_sentence_output'] = bool(first['sentences'])
        checks['avatar_expression_extraction'] = any(s['actions'].get('expressions') for s in first['sentences'])
        checks['tts_text_preprocessing'] = all('[joy]' not in s['tts_text'] for s in first['sentences'])
        second = await turn(bridge, '我剛剛說我叫什麼、喝什麼？')
        answer = ''.join(s['display_text'] for s in second['sentences'])
        checks['conversation_recall'] = '晨星' in answer and '烏龍茶' in answer
        snapshot = [{'role': m.role, 'content': m.content} for m in bridge.runtime.history]
        # Round-trip through JSON and a new runtime, without touching user history.
        restored = new_bridge()
        restored.restore_history([Message(**m) for m in json.loads(json.dumps(snapshot))])
        third = await turn(restored, '請再說一次我的名字和今天的飲料。')
        answer = ''.join(s['display_text'] for s in third['sentences'])
        checks['history_restore_recall'] = '晨星' in answer and '烏龍茶' in answer
        checks['no_user_config_changes'] = before == hashlib.sha256(config_path.read_bytes()).hexdigest()
        report = {'engine_version': __version__, 'python': sys.version.split()[0],
                  'model_endpoint': 'http://127.0.0.1:1234/v1', 'model': args.model,
                  'checks': checks, 'passed': all(checks.values()), 'turns': records,
                  'scope': 'Tomoshibi BatchInput, engine turns/streaming/history, real host SentenceOutput and expression/TTS-text processing',
                  'not_exercised': ['full application agent replacement', 'audio synthesis/playback', 'ASR', 'camera/screen', 'MCP/search', 'background cognition']}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
        print(json.dumps(checks, ensure_ascii=False), flush=True)
        if not report['passed']:
            raise RuntimeError('One or more integration checks failed; see report')
        if args.interactive:
            print('輸入文字試聊；輸入 /quit 結束。')
            while True:
                text = await asyncio.to_thread(input, 'You: ')
                if text.strip() == '/quit':
                    break
                if text.strip():
                    await turn(restored, text)
    finally:
        for bridge in bridges:
            await bridge.close()
        await client.client.close()


if __name__ == '__main__':
    args = arguments()
    args.output = args.output.resolve()
    asyncio.run(main(args))
