/* eslint-disable import/no-extraneous-dependencies */
// 角色管理分頁：清單 + 建立表單 + 編輯表單。跟 LLM／About 一樣是無 props 的
// 分頁（見 setting-ui.tsx 的三處註冊）——存檔／建立是即時打 API，不需要外層
// 抽屜的 Save/Cancel 去觸發，所以不接 onSave/onCancel。
//
// 送出一律先用 buildCharacterUpdate 把 draft 疊在現值上再送出：draft 本身在
// 進入編輯畫面時就用「現值 ?? ''」完整初始化成四個真正的字串（見
// openEdit），從頭到尾不會出現 undefined，所以整包 draft 傳給
// buildCharacterUpdate 是安全的——不會誤觸「鍵存在就代表使用者編輯過」而把
// 使用者沒碰過的欄位清空（Task 2 review 點名的那個資料遺失陷阱）。
//
// 建立表單（Task 2c-3）刻意重用編輯表單的兩個既有機制，而不是另寫一套：
// 皮膚／語音選單共用同一份 skinCollection／voiceCollection，語音選單也沿用
// INHERIT_VOICE 這個畫面用哨兵值（Chakra v3 的 Select 沒辦法區分「選了空字
// 串」跟「沒有選擇」，兩者的 value.toString() 都是空字串）。三個必填欄位
// （conf_name/persona_prompt/live2d_model_name）不在前端擋，交給
// POST /api/characters 用帶訊息的 400 驗證——原因見 handleCreate 旁的註解。
import {
  useState, useEffect, useMemo, useCallback, useRef,
} from 'react';
// 遷移中：表單控制項已改用 Ark UI + Tailwind（common-tw），版面容器（Stack／
// HStack／Text／Heading）仍是 Chakra。createListCollection 從 Ark 直接拿，理由
// 同 asr.tsx——Chakra 現在只是把 Ark 的原樣 re-export，那是巧合不是契約。
import {
  Stack, Box, Text, Heading, HStack,
} from '@chakra-ui/react';
import { createListCollection } from '@ark-ui/react/collection';
import { useTranslation } from 'react-i18next';
import { settingStyles } from './setting-styles';
import { toaster } from '@/components/ui/tw/toaster';
import { useWebSocket } from '@/context/websocket-context';
import { useConfig } from '@/context/character-config-context';
import { useSwitchCharacter } from '@/hooks/utils/use-switch-character';
import {
  SelectField, InputField, TextareaField, Field, Button,
} from './common';
import {
  fetchCharacters,
  fetchLive2dSkins,
  fetchVoices,
  updateCharacter,
  createCharacter,
  buildCharacterUpdate,
  uploadAvatar,
  validateAvatarFile,
  type CharacterRecord,
  type CharacterEdits,
  type CharacterCreate,
  type OptionalCharacterFields,
} from '@/api/characters.ts';
import { buildUrl, normalizeError } from '@/api/http.ts';
import { fetchPerf, type PerfState } from '@/api/perf.ts';
import { gptSovitsLangLabelKey } from '@/utils/gpt-sovits-langs';
import { ttsModelLabelKey } from '@/utils/tts-models';

interface SkinOption {
  name: string
}

interface VoiceOption {
  value: string
  label: string
}

// GPT-SoVITS 的參考音。path 是絕對路徑（後端要的），label 是檔名（給人看的），
// prompt_text 來自同名的 .txt sidecar——選了就一起填，兩者是一組的。
interface ReferenceVoice {
  path: string
  label: string
  prompt_text: string
}

// 建立表單的草稿。跟 CharacterEdits 的四個必填欄位相同，另外多一個 slug——
// 這是建立獨有的（更新不能改檔名/slug），所以不併進 CharacterEdits。
// voice 一樣用畫面用的哨兵值（INHERIT_VOICE），送出前才轉換。character_name／
// avatar 是 2c-3 新增的兩個選填欄位，建立時沒有「現值」可比對，留空就代表
// 不送（見 handleCreate 旁的說明）。
interface CreateDraft {
  conf_name: string
  persona_prompt: string
  live2d_model_name: string
  voice: string
  slug: string
  character_name: string
  avatar: string
  reply_language: string
  voice_lang: string
  tts_model: string
  ref_audio_path: string
  prompt_text: string
  prompt_lang: string
}

// 編輯表單的草稿。在 CharacterEdits 的四個必填欄位之外，多帶 character_name／
// avatar 這兩個選填欄位的「畫面現值」，好讓 handleSave 能跟 selectedRecord 的
// 現值比對，判斷使用者到底有沒有真的改過（見 handleSave 旁的說明）。
interface EditDraft extends CharacterEdits {
  character_name: string
  avatar: string
  reply_language: string
  voice_lang: string
  tts_model: string
  ref_audio_path: string
  prompt_text: string
  prompt_lang: string
}

// 後端試聽逾時 12 秒（VOICE_SAMPLE_TIMEOUT in character_route.py），前端多留
// 1 秒緩衝再自己中止，避免請求卡死。
const VOICE_SAMPLE_TIMEOUT_MS = 13000;

// 發聲語言的「沿用全域設定」。跟 INHERIT_VOICE 是同一個 zag-js 陷阱（見下方
// 說明）：空字串當 Select 的 value 無法跟「沒有選擇」區分，所以畫面上改用這個
// 非空哨兵值，只在讀取現值／送出前轉換成後端認得的空字串。
const INHERIT_LANG = '__inherit__';

// 「沿用預設聲音」在資料層是空字串（CharacterRecord.voice === '' / null），但
// 不能拿空字串當 SelectField 的 value：Chakra 的 Select（zag-js）用
// `value.toString()` 追蹤變化，而 [''].toString() 和 [].toString() 都是 ''，
// 兩者無法區分，於是「已選擇空字串」永遠被誤判成「沒有選擇」，UI 只會顯示
// placeholder，選不出「沿用預設聲音」這個選項（實測驗證過）。所以在畫面上用
// 這個非空字串的哨兵值代表它，只在讀取現值／送出前才轉換成真正的空字串。
const INHERIT_VOICE = '__inherit__';

// 「沿用 conf.yaml 的引擎」——跟 INHERIT_VOICE／INHERIT_LANG 同一個 zag-js 陷阱，
// 理由見上面那兩段。這個欄位是為了修「角色面板一存檔，聲音就被切回內建語音」
// 加的：後端以前寫死 tts_config.tts_model = edge_tts，畫面上完全看不到這件事。
const INHERIT_ENGINE = '__inherit__';

function Characters(): JSX.Element {
  const { t } = useTranslation();
  const { baseUrl } = useWebSocket();
  const { confName } = useConfig();
  const { switchCharacter } = useSwitchCharacter();

  const [characters, setCharacters] = useState<CharacterRecord[] | null>(null);
  const [listError, setListError] = useState<string | null>(null);
  const [refreshTick, setRefreshTick] = useState(0);

  const [skins, setSkins] = useState<SkinOption[]>([]);
  const [skinsLoading, setSkinsLoading] = useState(true);
  // 發聲語言的允許清單來自 /api/perf 的 gpt_sovits_langs——跟語音合成分頁同一份
  // single source of truth（後端 perf_route.py 的 GPT_SOVITS_LANGS）。抓不到就
  // 留空，下面的欄位會整個不顯示，而不是給一份會漂移的硬編清單。
  const [voiceLangs, setVoiceLangs] = useState<string[]>([]);
  // 可直接選用的參考音（後端掃 conf.yaml 那個 ref_audio_path 的所在資料夾）。
  const [referenceVoices, setReferenceVoices] = useState<ReferenceVoice[]>([]);
  // 可選的 TTS 引擎清單，跟 voiceLangs 同一次 GET /api/perf 拿到。
  const [ttsModels, setTtsModels] = useState<string[]>([]);
  const [skinsError, setSkinsError] = useState<string | null>(null);

  const [voices, setVoices] = useState<VoiceOption[]>([]);
  const [voicesLoading, setVoicesLoading] = useState(true);
  const [voicesError, setVoicesError] = useState<string | null>(null);
  const [loadingFullVoices, setLoadingFullVoices] = useState(false);
  const [voicesAreFull, setVoicesAreFull] = useState(false);

  const [selectedFilename, setSelectedFilename] = useState<string | null>(null);
  const [draft, setDraft] = useState<EditDraft | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const [showCreateForm, setShowCreateForm] = useState(false);
  const [createDraft, setCreateDraft] = useState<CreateDraft | null>(null);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const [pendingDeleteFilename, setPendingDeleteFilename] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const [previewingVoice, setPreviewingVoice] = useState<string | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const objectUrlRef = useRef<string | null>(null);

  // 頭像上傳狀態。跟 previewingVoice/previewError 一樣是建立表單／編輯表單共用
  // 的頂層 state——兩個表單互斥顯示，所以不會互相干擾，但切換表單時要記得重置
  // （openCreate/openEdit/closeCreateForm/closeEdit 都會清），否則會像 Task 2
  // review 抓到的 previewError 那樣，殘留上一個表單的錯誤訊息。
  const [avatarUploading, setAvatarUploading] = useState(false);
  const [avatarUploadError, setAvatarUploadError] = useState<string | null>(null);
  const createAvatarInputRef = useRef<HTMLInputElement | null>(null);
  const editAvatarInputRef = useRef<HTMLInputElement | null>(null);

  // 「目前是哪一個表單/哪一筆紀錄在編輯」的世代號。openEdit/openCreate/closeEdit/
  // closeCreateForm 每次呼叫都會遞增這個 ref。頭像上傳是非同步的（runAvatarUpload
  // 內部會 await fetch），使用者可能在上傳完成前就按 Cancel 切到別的角色，或切去
  // 另一個表單——這時上傳完成時的 setDraft/setCreateDraft 仍會用「舊表單的
  // callback」執行，若不檢查世代號，就會把 A 角色上傳的檔名寫進 B 角色的 draft
  // 裡（final review 抓到的靜默寫錯紀錄）。做法：呼叫上傳前先記下當時的世代號，
  // 上傳完成後跟 ref 的當下值比對，不一致就整個結果（含錯誤訊息、loading 旗標）
  // 都丟棄不寫，避免舊表單的延遲錯誤訊息冒出現在新表單上（同一機制順便解決
  // avatarUploading/avatarUploadError 在兩個表單間串味的問題）。
  const formSessionRef = useRef(0);

  // 角色清單。refreshTick 讓存檔/刪除成功後可以重新拉一次，不用整頁重載。
  useEffect(() => {
    let cancelled = false;
    setListError(null);
    (async () => {
      const result = await fetchCharacters(baseUrl);
      if (cancelled) return;
      if (result.ok) {
        setCharacters(result.data.characters);
      } else {
        setCharacters((prev) => prev ?? []);
        setListError(result.error);
      }
    })();
    return (): void => {
      cancelled = true;
    };
  }, [baseUrl, refreshTick]);

  // Live2D 外觀清單。
  useEffect(() => {
    let cancelled = false;
    setSkinsLoading(true);
    setSkinsError(null);
    (async () => {
      const result = await fetchLive2dSkins(baseUrl);
      if (cancelled) return;
      if (result.ok) {
        const data = result.data as { skins?: { name: string }[] };
        setSkins(Array.isArray(data.skins) ? data.skins.map((s) => ({ name: s.name })) : []);
      } else {
        setSkinsError(result.error);
      }
      setSkinsLoading(false);
    })();
    return (): void => {
      cancelled = true;
    };
  }, [baseUrl]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const result = await fetchPerf(baseUrl);
      if (cancelled) return;
      if (result.ok) {
        const data = result.data as PerfState;
        setVoiceLangs(Array.isArray(data.gpt_sovits_langs) ? data.gpt_sovits_langs : []);
        setTtsModels(Array.isArray(data.tts_models) ? data.tts_models : []);
        setReferenceVoices(
          Array.isArray(data.reference_voices) ? data.reference_voices : [],
        );
      }
      // 失敗不顯示錯誤：這只是一個選填欄位的選項來源，表單其餘部分照常可用。
    })();
    return (): void => {
      cancelled = true;
    };
  }, [baseUrl]);

  // 精選語音（預設，不帶 full）。
  useEffect(() => {
    let cancelled = false;
    setVoicesLoading(true);
    setVoicesError(null);
    (async () => {
      const result = await fetchVoices(baseUrl);
      if (cancelled) return;
      if (result.ok) {
        const data = result.data as { voices?: VoiceOption[] };
        setVoices(Array.isArray(data.voices) ? data.voices : []);
      } else {
        setVoicesError(result.error);
      }
      setVoicesLoading(false);
    })();
    return (): void => {
      cancelled = true;
    };
  }, [baseUrl]);

  // 使用者主動要求完整清單（?full=1，約 150 筆，後端會即時打一次
  // edge_tts.list_voices()）——預設只顯示 9 個精選語音，這裡才拉完整清單。
  const handleShowAllVoices = useCallback(async () => {
    setLoadingFullVoices(true);
    setVoicesError(null);
    const result = await fetchVoices(baseUrl, true);
    setLoadingFullVoices(false);
    if (result.ok) {
      const data = result.data as { voices?: VoiceOption[] };
      setVoices(Array.isArray(data.voices) ? data.voices : []);
      setVoicesAreFull(true);
    } else {
      setVoicesError(result.error);
    }
  }, [baseUrl]);

  const skinCollection = useMemo(
    () => createListCollection({
      items: skins.map((s) => ({ label: s.name, value: s.name })),
    }),
    [skins],
  );

  const voiceCollection = useMemo(() => {
    const items = [
      { label: t('settings.characters.inheritVoice'), value: INHERIT_VOICE },
      ...voices.map((v) => ({ label: v.label, value: v.value })),
    ];
    // 角色現有的聲音可能不在精選 9 個之列（例如 conf.yaml 手動填過別的 ShortName）。
    // 沒有這個保底項的話，SelectField 找不到相符的 collection item，觸發器只會
    // 顯示 placeholder——看起來像是聲音欄位被清空了，但其實 draft.voice 裡的值
    // 完好無缺，只是選單畫不出來。所以只要現值沒出現在清單裡就補一項進去，
    // 使用者不動它、直接存檔，也不會被這裡的顯示問題誤導去手動重選。
    // 兩個表單互斥顯示（同時只有一個的 draft 非 null），用 ?? 取「目前開著的
    // 那個表單」的畫面現值即可——單獨只看 draft?.voice 的話，建立表單選了一個
    // 不在精選清單裡的語音（例如 showAllVoices 選到、又切回精選清單）時，觸發器
    // 一樣會退回 placeholder，跟 draft 那個 bug 是同一個成因，只是發生在另一個
    // 表單（Task 2c-3 從編輯表單複製出建立表單時漏收斂的第一個 drift 案例）。
    const current = draft?.voice ?? createDraft?.voice;
    if (current && current !== INHERIT_VOICE && !items.some((item) => item.value === current)) {
      items.push({ label: current, value: current });
    }
    return createListCollection({ items });
  }, [voices, t, draft?.voice, createDraft?.voice]);

  // 發聲語言下拉。第一項是「沿用全域設定」的哨兵值，後面照後端清單排。
  const voiceLangCollection = useMemo(() => {
    const items = [
      { label: t('settings.characters.voiceLangInherit'), value: INHERIT_LANG },
      ...voiceLangs.map((code) => {
        const key = gptSovitsLangLabelKey(code);
        return { label: key ? t(key) : code, value: code };
      }),
    ];
    // 跟 voiceCollection 同一個保底：角色檔的 text_lang 是手寫的 YAML，可能是
    // 後端清單以外的值（GPT-SoVITS 自己還吃 all_ja、all_zh 這類混合代碼）。
    // 沒有保底項的話觸發器只會顯示 placeholder，看起來像是沒設定，實際上值
    // 好端端地在角色檔裡——而使用者一存檔就真的被改掉了。
    const current = draft?.voice_lang ?? createDraft?.voice_lang;
    if (current && current !== INHERIT_LANG && !items.some((item) => item.value === current)) {
      items.push({ label: current, value: current });
    }
    return createListCollection({ items });
  }, [voiceLangs, t, draft?.voice_lang, createDraft?.voice_lang]);

  // 參考音下拉。第一項是「沿用全域設定」（＝清掉，用 conf.yaml 那份），後面是
  // 掃到的檔案。手寫在 YAML 裡、不在資料夾內的路徑要有保底項，否則觸發器只顯示
  // placeholder，看起來像沒設定，一存檔就真的被清掉。
  const refAudioCollection = useMemo(() => {
    const items = [
      { label: t('settings.characters.refAudioInherit'), value: INHERIT_VOICE },
      ...referenceVoices.map((v) => ({ label: v.label, value: v.path })),
    ];
    const current = draft?.ref_audio_path ?? createDraft?.ref_audio_path;
    if (current && !items.some((i) => i.value === current)) {
      // 只顯示檔名，完整路徑太長會把觸發器撐爆
      items.push({ label: current.split('/').pop() || current, value: current });
    }
    return createListCollection({ items });
  }, [referenceVoices, t, draft?.ref_audio_path, createDraft?.ref_audio_path]);

  // 選了參考音就順手把逐字稿填上。參考音跟逐字稿是一組的，分開填等於留一個
  // 「對不起來就靜默壞掉」的機會給使用者。
  const promptTextFor = useCallback(
    (path: string) => referenceVoices.find((v) => v.path === path)?.prompt_text ?? '',
    [referenceVoices],
  );

  // 參考音的語言。值域跟發聲語言同一份（都是 GPT-SoVITS 的語言代碼），但保底項
  // 必須跟著 prompt_lang 自己的現值走，所以不能共用 voiceLangCollection——共用的
  // 話，角色檔裡手寫的 prompt_lang 若不在後端清單內就會被靜默清掉。
  const promptLangCollection = useMemo(() => {
    const items = [
      { label: t('settings.characters.promptLangInherit'), value: INHERIT_LANG },
      ...voiceLangs.map((code) => {
        const key = gptSovitsLangLabelKey(code);
        return { label: key ? t(key) : code, value: code };
      }),
    ];
    const current = draft?.prompt_lang ?? createDraft?.prompt_lang;
    if (current && current !== INHERIT_LANG && !items.some((item) => item.value === current)) {
      items.push({ label: current, value: current });
    }
    return createListCollection({ items });
  }, [voiceLangs, t, draft?.prompt_lang, createDraft?.prompt_lang]);

  // TTS 引擎下拉。值域用後端 GET /api/perf 回的 tts_models，跟合成分頁
  // （tts.tsx）同一份來源，不另外寫死一張清單。第一項是「沿用全域設定」。
  const engineCollection = useMemo(() => {
    const items = [
      { label: t('settings.characters.ttsEngineInherit'), value: INHERIT_ENGINE },
      ...ttsModels.map((name) => {
        const key = ttsModelLabelKey(name);
        return { label: key ? t(key) : name, value: name };
      }),
    ];
    // 同樣的保底：角色檔的 tts_model 是手寫 YAML，可能是後端清單以外的值。
    // 沒有保底項時觸發器只顯示 placeholder，看起來像沒設定，一存檔就真的被清掉。
    const current = draft?.tts_model ?? createDraft?.tts_model;
    if (current && current !== INHERIT_ENGINE && !items.some((i) => i.value === current)) {
      items.push({ label: current, value: current });
    }
    return createListCollection({ items });
  }, [ttsModels, t, draft?.tts_model, createDraft?.tts_model]);

  const selectedRecord = useMemo(
    () => (characters ?? []).find((c) => c.filename === selectedFilename) ?? null,
    [characters, selectedFilename],
  );

  const openEdit = useCallback((record: CharacterRecord) => {
    // 遞增世代號：任何還在飛的頭像上傳（不論屬於哪個表單）從這一刻起都是舊世代，
    // 完成時會被 handleCreateAvatarFile/handleEditAvatarFile 的世代檢查丟棄。
    formSessionRef.current += 1;
    // 清單頁一次只會開一種表單，但仍主動關掉建立表單以確保互斥，避免兩個
    // 全頁表單狀態同時為真的邊界情況。
    setShowCreateForm(false);
    setCreateDraft(null);
    setCreateError(null);
    setSelectedFilename(record.filename);
    // 每個欄位都用「現值 ?? ''」填成真正的字串，永遠不會是 undefined。
    // character_name/avatar/reply_language/voice_lang 額外存一份「畫面現值」，
    // 是為了 handleSave 能跟 selectedRecord 的原始值比對，判斷是否真的被編輯過。
    setDraft({
      conf_name: record.conf_name ?? '',
      persona_prompt: record.persona_prompt ?? '',
      live2d_model_name: record.live2d_model_name ?? '',
      voice: record.voice || INHERIT_VOICE,
      character_name: record.character_name ?? '',
      avatar: record.avatar ?? '',
      reply_language: record.reply_language ?? '',
      voice_lang: record.voice_lang || INHERIT_LANG,
      tts_model: record.tts_model || INHERIT_ENGINE,
      // 參考音三件套是自由輸入，沒有 Select 的空字串陷阱，直接用現值即可。
      ref_audio_path: record.ref_audio_path || '',
      prompt_text: record.prompt_text || '',
      prompt_lang: record.prompt_lang || INHERIT_LANG,
    });
    setSaveError(null);
    setPreviewError(null);
    setAvatarUploadError(null);
    setAvatarUploading(false);
  }, []);

  const closeEdit = useCallback(() => {
    // 同上：切換/關閉表單即代表這個世代結束，任何仍在飛的上傳完成時都該被忽略。
    formSessionRef.current += 1;
    setSelectedFilename(null);
    setDraft(null);
    setSaveError(null);
    setAvatarUploadError(null);
    setAvatarUploading(false);
  }, []);

  const openCreate = useCallback(() => {
    formSessionRef.current += 1;
    setSelectedFilename(null);
    setDraft(null);
    setSaveError(null);
    setCreateDraft({
      conf_name: '',
      persona_prompt: '',
      live2d_model_name: '',
      voice: INHERIT_VOICE,
      slug: '',
      character_name: '',
      avatar: '',
      reply_language: '',
      voice_lang: INHERIT_LANG,
      tts_model: INHERIT_ENGINE,
      ref_audio_path: '',
      prompt_text: '',
      prompt_lang: INHERIT_LANG,
    });
    setCreateError(null);
    // 修正 Task 2 review 抓到的資料殘留：openEdit 一直有清 previewError，
    // openCreate 沒有——先前在編輯表單試聽失敗過，接著開建立表單會沿用同一顆
    // previewError state，錯誤訊息就會莫名其妙地出現在全新的建立表單裡。
    setPreviewError(null);
    setAvatarUploadError(null);
    setAvatarUploading(false);
    setShowCreateForm(true);
  }, []);

  const closeCreateForm = useCallback(() => {
    formSessionRef.current += 1;
    setShowCreateForm(false);
    setCreateDraft(null);
    setCreateError(null);
    setAvatarUploadError(null);
    setAvatarUploading(false);
  }, []);

  const handleSave = useCallback(async () => {
    if (!selectedRecord || !draft) return;

    if (!draft.conf_name.trim()) {
      setSaveError(t('settings.characters.errNameRequired'));
      return;
    }
    if (!draft.persona_prompt.trim()) {
      setSaveError(t('settings.characters.errPersonaRequired'));
      return;
    }
    if (!draft.live2d_model_name.trim()) {
      setSaveError(t('settings.characters.errSkinRequired'));
      return;
    }

    setSaving(true);
    setSaveError(null);
    // draft.voice 是畫面用的哨兵值，送出前換回後端認得的空字串（= 沿用預設聲音）。
    // 只列四個必填欄位，不用 ...draft 展開——draft 這個 EditDraft 還帶著
    // character_name/avatar/reply_language/voice_lang 這些選填欄位的「畫面現
    // 值」，那些不透過這裡送，而是下面用 optional 參數另外決定（見下方註解）。
    const edits: CharacterEdits = {
      conf_name: draft.conf_name,
      persona_prompt: draft.persona_prompt,
      live2d_model_name: draft.live2d_model_name,
      voice: draft.voice === INHERIT_VOICE ? '' : draft.voice,
    };
    // character_name/avatar 只在「畫面現值跟 selectedRecord 的原始值不同」時才
    // 放進 optional，未編輯就完全不放這個鍵——buildCharacterUpdate 對「鍵不存在」
    // 跟「值是 undefined」一視同仁地當成未編輯，但這裡刻意直接不放鍵，而不是
    // 放一個 undefined 進去，讓「有沒有送這個欄位」在建構的當下就是明確的，不
    // 依賴 buildCharacterUpdate 的 undefined 過濾當保險。
    //
    // character_name 比對前先 trim：後端 _extract_body_fields 對 character_name
    // 不會 strip（跟 avatar 不同，character_route.py:557 vs :566），
    // _build_character_config 的 `character_name or conf_name` 只有在空字串時
    // 才會退回角色名稱，所以打了一串空白的名字會被逐字存成顯示名稱。這裡先
    // trim 再比較、也送 trim 後的值，讓「只打空白」等同於「留空＝沿用角色名稱」
    // 這個 aiNameHelp 文案講的行為。
    const optional: OptionalCharacterFields = {};
    const trimmedName = draft.character_name.trim();
    const originalName = (selectedRecord.character_name ?? '').trim();
    if (trimmedName !== originalName) {
      optional.character_name = trimmedName;
    }
    const originalAvatar = selectedRecord.avatar ?? '';
    if (draft.avatar !== originalAvatar) {
      optional.avatar = draft.avatar;
    }
    // 兩個語言欄位同樣是「沒改就整個鍵不送」——後端 update_character 對缺鍵的
    // 處理是退回磁碟現值，送空字串才是清除。reply_language 跟 character_name
    // 一樣先 trim 再比較（後端也 strip），免得一串空白被存成語言名稱，變成一句
    // 要求她「用　　　回答」的提示詞。
    const trimmedReplyLang = draft.reply_language.trim();
    if (trimmedReplyLang !== (selectedRecord.reply_language ?? '').trim()) {
      optional.reply_language = trimmedReplyLang;
    }
    // voice_lang 在畫面上是哨兵值，送出前轉回空字串（= 沿用 conf.yaml 的全域值）。
    const voiceLang = draft.voice_lang === INHERIT_LANG ? '' : draft.voice_lang;
    if (voiceLang !== (selectedRecord.voice_lang ?? '')) {
      optional.voice_lang = voiceLang;
    }
    // 引擎同樣是哨兵值 → 空字串（＝不釘，沿用 conf.yaml）。沒改就整個鍵不送，
    // 後端遇到缺鍵會退回磁碟現值——這正是修好「一直被切回去」的另一半。
    const ttsModel = draft.tts_model === INHERIT_ENGINE ? '' : draft.tts_model;
    if (ttsModel !== (selectedRecord.tts_model ?? '')) {
      optional.tts_model = ttsModel;
    }
    // 參考音三件套走跟上面完全一樣的規則：沒改就整個鍵不送（後端退回磁碟現值），
    // 改成空字串才是「清掉，改回沿用 conf.yaml 的全域參考音」。
    const refAudio = draft.ref_audio_path.trim();
    if (refAudio !== (selectedRecord.ref_audio_path ?? '').trim()) {
      optional.ref_audio_path = refAudio;
    }
    const promptText = draft.prompt_text.trim();
    if (promptText !== (selectedRecord.prompt_text ?? '').trim()) {
      optional.prompt_text = promptText;
    }
    const promptLang = draft.prompt_lang === INHERIT_LANG ? '' : draft.prompt_lang;
    if (promptLang !== (selectedRecord.prompt_lang ?? '')) {
      optional.prompt_lang = promptLang;
    }
    const body = buildCharacterUpdate(selectedRecord, edits, optional);
    const result = await updateCharacter(baseUrl, selectedRecord.filename, body);
    setSaving(false);

    if (result.ok) {
      const wasActive = selectedRecord.conf_name === confName;
      toaster.create({
        title: t('settings.characters.saved', { name: draft.conf_name }),
        description: wasActive ? t('settings.characters.appliedHint') : undefined,
        type: 'success',
        duration: 2500,
      });
      setRefreshTick((n) => n + 1);
      closeEdit();
      if (wasActive) {
        switchCharacter(selectedRecord.filename, true);
      }
    } else {
      setSaveError(result.error || t('settings.characters.errSaveFailed'));
    }
  }, [selectedRecord, draft, baseUrl, t, closeEdit, confName, switchCharacter]);

  // 三個必填欄位（conf_name/persona_prompt/live2d_model_name）刻意不在前端擋——
  // POST /api/characters 本來就會各自回帶訊息的 400，且皮膚是否已註冊也只有
  // 後端知道，前端再驗一次只是多一份會漂移的規則（見檔頭與 task brief）。
  const handleCreate = useCallback(async () => {
    if (!createDraft) return;

    setCreating(true);
    setCreateError(null);
    // createDraft.voice 是畫面用的哨兵值，送出前換回後端認得的空字串（= 沿用預設聲音）。
    const body: CharacterCreate = {
      conf_name: createDraft.conf_name,
      persona_prompt: createDraft.persona_prompt,
      live2d_model_name: createDraft.live2d_model_name,
      voice: createDraft.voice === INHERIT_VOICE ? '' : createDraft.voice,
    };
    if (createDraft.slug.trim()) {
      body.slug = createDraft.slug.trim();
    }
    // 跟編輯表單一樣先 trim 再判斷要不要送：建立時沒有「現值」可比對，但同一個
    // 空白字元陷阱仍然存在（見 handleSave 旁的說明），所以 trim 後留空就完全不
    // 送這個鍵，讓後端自己用 conf_name 頂上，而不是把一串空白存成顯示名稱。
    const trimmedName = createDraft.character_name.trim();
    if (trimmedName) {
      body.character_name = trimmedName;
    }
    if (createDraft.avatar) {
      body.avatar = createDraft.avatar;
    }
    const trimmedReplyLang = createDraft.reply_language.trim();
    if (trimmedReplyLang) {
      body.reply_language = trimmedReplyLang;
    }
    if (createDraft.voice_lang && createDraft.voice_lang !== INHERIT_LANG) {
      body.voice_lang = createDraft.voice_lang;
    }
    // 建立表單一直有 TTS 引擎選單，但這裡從來沒把它送出去——選了 gpt_sovits_tts
    // 建出來的角色仍然沿用 conf.yaml 的引擎，畫面上沒有任何線索。
    if (createDraft.tts_model && createDraft.tts_model !== INHERIT_ENGINE) {
      body.tts_model = createDraft.tts_model;
    }
    // 參考音三件套：決定「用誰的聲音」。留空＝沿用 conf.yaml 的全域參考音。
    const trimmedRefAudio = createDraft.ref_audio_path.trim();
    if (trimmedRefAudio) {
      body.ref_audio_path = trimmedRefAudio;
    }
    const trimmedPromptText = createDraft.prompt_text.trim();
    if (trimmedPromptText) {
      body.prompt_text = trimmedPromptText;
    }
    if (createDraft.prompt_lang && createDraft.prompt_lang !== INHERIT_LANG) {
      body.prompt_lang = createDraft.prompt_lang;
    }
    const result = await createCharacter(baseUrl, body);
    setCreating(false);

    if (result.ok) {
      toaster.create({
        title: t('settings.characters.created', { name: createDraft.conf_name }),
        type: 'success',
        duration: 2500,
      });
      setRefreshTick((n) => n + 1);
      closeCreateForm();
    } else {
      setCreateError(result.error || t('settings.characters.errSaveFailed'));
    }
  }, [createDraft, baseUrl, t, closeCreateForm]);

  // DELETE 沒有 apiDelete 包裝（http.ts 只有 GET/POST/PUT），所以直接用原生
  // fetch，但仍重用 http.ts 已匯出的 buildUrl／normalizeError，維持跟其他請求
  // 一致的 URL 組法與錯誤訊息正規化。
  const handleDelete = useCallback(async (filename: string) => {
    setDeleting(true);
    setDeleteError(null);
    const url = buildUrl(baseUrl, `/api/characters/${encodeURIComponent(filename)}`);
    const deletedName = (characters ?? []).find((c) => c.filename === filename)?.conf_name
      || filename;
    try {
      const res = await fetch(url, { method: 'DELETE' });
      let parsed: unknown = null;
      try {
        parsed = await res.json();
      } catch {
        // 非 JSON 回應：normalizeError 會退回含狀態碼的字串
      }
      if (!res.ok) {
        setDeleteError(normalizeError(parsed, res.status));
        setDeleting(false);
        return;
      }
      toaster.create({
        title: t('settings.characters.deleted', { name: deletedName }),
        type: 'success',
        duration: 2500,
      });
      setDeleting(false);
      setPendingDeleteFilename(null);
      setRefreshTick((n) => n + 1);
    } catch (e) {
      setDeleting(false);
      setDeleteError(e instanceof Error ? e.message : t('settings.characters.errDeleteFailed'));
    }
  }, [baseUrl, characters, t]);

  // 試聽：GET /api/voice-sample 回 audio/mpeg 位元組，不是 JSON，apiGet 對這個
  // 端點不適用。改用原生 fetch 取 blob 再用 URL.createObjectURL 播放；後端逾時
  // 12 秒，這裡的 previewingVoice 狀態就是那段等待的載入指示。
  const handlePreview = useCallback(async (voice: string) => {
    if (!voice || voice === INHERIT_VOICE) return;
    setPreviewingVoice(voice);
    setPreviewError(null);
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), VOICE_SAMPLE_TIMEOUT_MS);
    try {
      const url = buildUrl(baseUrl, `/api/voice-sample?voice=${encodeURIComponent(voice)}`);
      const res = await fetch(url, { signal: controller.signal });
      if (!res.ok) {
        let parsed: unknown = null;
        try {
          parsed = await res.json();
        } catch {
          // ignore：非 JSON 錯誤內容
        }
        setPreviewError(normalizeError(parsed, res.status));
        return;
      }
      const blob = await res.blob();
      if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
      const objectUrl = URL.createObjectURL(blob);
      objectUrlRef.current = objectUrl;
      if (!audioRef.current) audioRef.current = new Audio();
      audioRef.current.src = objectUrl;
      await audioRef.current.play();
    } catch {
      setPreviewError(t('settings.characters.previewFailed'));
    } finally {
      clearTimeout(timer);
      setPreviewingVoice(null);
    }
  }, [baseUrl, t]);

  // 卸载時釋放最後一個 object URL，避免記憶體洩漏。
  useEffect(() => () => {
    if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
  }, []);

  // 頭像選檔＋驗證＋上傳共用的核心邏輯，建立表單／編輯表單各自的
  // handle*AvatarFile 只差在上傳成功後要塞回哪個 state（createDraft 或
  // draft），所以把「驗證 → 上傳 → 回傳結果」抽成這一個不碰 state 的純異步
  // 函式，呼叫端各自決定成功/失敗要做什麼。先驗型別與大小（validateAvatarFile
  // 回傳 i18n 鍵，這裡就地轉成顯示字串），驗過才真的打 uploadAvatar。
  const runAvatarUpload = useCallback(async (
    file: File,
    confUid?: string,
  ): Promise<{ ok: true; filename: string } | { ok: false; error: string }> => {
    const validationKey = validateAvatarFile(file);
    if (validationKey) {
      return { ok: false, error: t(validationKey) };
    }
    const result = await uploadAvatar(baseUrl, file, confUid);
    if (result.ok) {
      return { ok: true, filename: result.data.filename };
    }
    return { ok: false, error: result.error };
  }, [baseUrl, t]);

  const handleCreateAvatarFile = useCallback(async (file: File) => {
    // 上傳開始前先記下當時的世代號。這段 await 期間使用者可能按 Cancel、
    // 切去編輯某個角色，甚至重新打開建立表單——這些操作都會讓
    // formSessionRef 遞增，讓下面的比對失敗，整包結果（含 loading／錯誤旗標）
    // 就地丟棄，不寫進任何 draft。
    const session = formSessionRef.current;
    setAvatarUploading(true);
    setAvatarUploadError(null);
    const result = await runAvatarUpload(file);
    if (formSessionRef.current !== session) return;
    setAvatarUploading(false);
    if (result.ok) {
      setCreateDraft((d) => (d ? { ...d, avatar: result.filename } : d));
    } else {
      setAvatarUploadError(result.error);
    }
  }, [runAvatarUpload]);

  const handleEditAvatarFile = useCallback(async (file: File) => {
    // 同上：世代號在呼叫當下鎖定要上傳給哪一筆紀錄，完成時跟目前世代號不同就代表
    // 使用者已經切走了（Cancel 或改開別的角色），結果整包丟棄——這正是修掉
    // 「A 上傳中途按 Cancel 開 B，A 的檔名寫進 B 的 draft」這個資料誤寫的關鍵。
    const session = formSessionRef.current;
    setAvatarUploading(true);
    setAvatarUploadError(null);
    const result = await runAvatarUpload(file, selectedRecord?.conf_uid ?? undefined);
    if (formSessionRef.current !== session) return;
    setAvatarUploading(false);
    if (result.ok) {
      setDraft((d) => (d ? { ...d, avatar: result.filename } : d));
    } else {
      setAvatarUploadError(result.error);
    }
  }, [runAvatarUpload, selectedRecord]);

  if (characters === null) {
    return (
      <Stack {...settingStyles.common.container}>
        <Text fontSize="sm" color="whiteAlpha.700">
          {t('settings.characters.loading')}
        </Text>
      </Stack>
    );
  }

  if (showCreateForm && createDraft) {
    return (
      <Stack {...settingStyles.common.container} maxW="none">
        <Heading size="sm">{t('settings.characters.addTitle')}</Heading>

        <InputField
          label={t('settings.characters.name')}
          value={createDraft.conf_name}
          onChange={(value) => setCreateDraft((d) => (d ? { ...d, conf_name: value } : d))}
          placeholder={t('settings.characters.namePlaceholder')}
        />

        <TextareaField
          label={t('settings.characters.persona')}
          help={t('settings.characters.personaHelp')}
          rows={8}
          placeholder={t('settings.characters.personaPlaceholder')}
          value={createDraft.persona_prompt}
          onChange={(value) => setCreateDraft((d) => (d ? { ...d, persona_prompt: value } : d))}
        />

        {skinsLoading ? (
          <Text fontSize="xs" color="whiteAlpha.600">{t('settings.characters.loadingOptions')}</Text>
        ) : skinsError ? (
          <Text fontSize="xs" color="red.300">{t('settings.characters.errLoadFailed')}</Text>
        ) : skins.length === 0 ? (
          <Text fontSize="xs" color="whiteAlpha.600">{t('settings.characters.noSkinsHint')}</Text>
        ) : (
          <SelectField
            label={t('settings.characters.skin')}
            value={createDraft.live2d_model_name ? [createDraft.live2d_model_name] : []}
            onChange={(value) => setCreateDraft((d) => (
              d ? { ...d, live2d_model_name: value[0] ?? '' } : d
            ))}
            collection={skinCollection}
            placeholder={t('settings.characters.skin')}
          />
        )}

        <Stack gap={2}>
          <SelectField
            label={t('settings.characters.voice')}
            value={[createDraft.voice]}
            onChange={(value) => setCreateDraft((d) => (
              d ? { ...d, voice: value[0] ?? INHERIT_VOICE } : d
            ))}
            collection={voiceCollection}
            placeholder={t('settings.characters.voice')}
          />
          <Text fontSize="xs" color="whiteAlpha.600">
            {t('settings.characters.voiceHelp')}
          </Text>
          <Text fontSize="xs" color="whiteAlpha.500">
            {t('settings.characters.voiceEngineNote')}
          </Text>
          <HStack>
            <Button
              size="xs"
              variant="outline"
              disabled={!createDraft.voice || createDraft.voice === INHERIT_VOICE}
              loading={previewingVoice === createDraft.voice}
              onClick={() => handlePreview(createDraft.voice)}
            >
              {previewingVoice === createDraft.voice
                ? t('settings.characters.previewing')
                : t('settings.characters.preview')}
            </Button>
            {!voicesAreFull && (
              <Button
                size="xs"
                variant="ghost"
                onClick={handleShowAllVoices}
                loading={loadingFullVoices}
                disabled={voicesLoading}
              >
                {t('settings.characters.showAllVoices')}
              </Button>
            )}
            {voicesLoading && (
              <Text fontSize="xs" color="whiteAlpha.600">{t('settings.characters.loadingOptions')}</Text>
            )}
          </HStack>
          {voicesError && (
            <Text fontSize="xs" color="red.300">{t('settings.characters.errLoadFailed')}</Text>
          )}
          {previewError && (
            <Text fontSize="xs" color="red.300">{previewError}</Text>
          )}
        </Stack>


        {/* 兩個語言欄位放在語音區塊之後：回覆語言決定她「用什麼語言寫」，發聲
            語言決定「用什麼語言唸」。兩者不同時後端會在合成前先翻譯一次，那是
            延遲的主要來源之一，所以文案要講清楚這件事。 */}
        <InputField
          label={t('settings.characters.replyLanguage')}
          value={createDraft.reply_language}
          onChange={(value) => setCreateDraft((d) => (d ? { ...d, reply_language: value } : d))}
          placeholder={t('settings.characters.replyLanguagePlaceholder')}
          help={t('settings.characters.replyLanguageHelp')}
        />

        {ttsModels.length > 0 && (
          <Stack gap={2}>
            <SelectField
              label={t('settings.characters.ttsEngine')}
              value={[createDraft.tts_model]}
              onChange={(value) => setCreateDraft((d) => (
                d ? { ...d, tts_model: value[0] ?? INHERIT_ENGINE } : d
              ))}
              collection={engineCollection}
              placeholder={t('settings.characters.ttsEngine')}
            />
            <Text fontSize="xs" color="whiteAlpha.600">
              {t('settings.characters.ttsEngineHelp')}
            </Text>
          </Stack>
        )}

        {voiceLangs.length > 0 && (
          <Stack gap={2}>
            <SelectField
              label={t('settings.characters.voiceLang')}
              value={[createDraft.voice_lang]}
              onChange={(value) => setCreateDraft((d) => (
                d ? { ...d, voice_lang: value[0] ?? INHERIT_LANG } : d
              ))}
              collection={voiceLangCollection}
              placeholder={t('settings.characters.voiceLang')}
            />
            <Text fontSize="xs" color="whiteAlpha.600">
              {t('settings.characters.voiceLangHelp')}
            </Text>
          </Stack>
        )}

        {/* 「用誰的聲音」——只對 GPT-SoVITS 有意義。三者是一組：聲線由參考音決定，
            逐字稿要跟那段音檔對得上，否則克隆出來的音色會歪。 */}
        <Stack gap={2}>
          <SelectField
            label={t('settings.characters.refAudioPath')}
            value={[createDraft.ref_audio_path || INHERIT_VOICE]}
            onChange={(value) => setCreateDraft((d) => {
              if (!d) return d;
              const picked = value[0] === INHERIT_VOICE ? '' : (value[0] ?? '');
              // 換了參考音就換逐字稿。挑不到（手寫路徑、或沒有 sidecar）就維持原值，
              // 不要拿空字串把使用者自己打的逐字稿洗掉。
              const transcript = promptTextFor(picked);
              return {
                ...d,
                ref_audio_path: picked,
                prompt_text: transcript || d.prompt_text,
              };
            })}
            collection={refAudioCollection}
            placeholder={t('settings.characters.refAudioPath')}
          />
          <Text fontSize="xs" color="whiteAlpha.600">
            {t('settings.characters.refAudioPathHelp')}
          </Text>
        </Stack>

        <InputField
          label={t('settings.characters.promptText')}
          value={createDraft.prompt_text}
          onChange={(value) => setCreateDraft((d) => (d ? { ...d, prompt_text: value } : d))}
          placeholder={t('settings.characters.promptTextPlaceholder')}
          help={t('settings.characters.promptTextHelp')}
        />

        {voiceLangs.length > 0 && (
          <Stack gap={2}>
            <SelectField
              label={t('settings.characters.promptLang')}
              value={[createDraft.prompt_lang]}
              onChange={(value) => setCreateDraft((d) => (
                d ? { ...d, prompt_lang: value[0] ?? INHERIT_LANG } : d
              ))}
              collection={promptLangCollection}
              placeholder={t('settings.characters.promptLang')}
            />
            <Text fontSize="xs" color="whiteAlpha.600">
              {t('settings.characters.promptLangHelp')}
            </Text>
          </Stack>
        )}

        <InputField
          label={t('settings.characters.slug')}
          value={createDraft.slug}
          onChange={(value) => setCreateDraft((d) => (d ? { ...d, slug: value } : d))}
          placeholder={t('settings.characters.slugPlaceholder')}
          help={t('settings.characters.slugHelp')}
        />

        <InputField
          label={t('settings.characters.aiName')}
          value={createDraft.character_name}
          onChange={(value) => setCreateDraft((d) => (d ? { ...d, character_name: value } : d))}
          help={t('settings.characters.aiNameHelp')}
        />

        <Field
          label={t('settings.characters.aiAvatar')}
          help={t('settings.characters.aiAvatarHelp')}
        >
          <HStack>
            <input
              ref={createAvatarInputRef}
              type="file"
              accept="image/*"
              style={{ display: 'none' }}
              onChange={(e) => {
                const file = e.target.files?.[0];
                e.target.value = '';
                if (file) handleCreateAvatarFile(file);
              }}
            />
            <Button
              size="xs"
              variant="outline"
              onClick={() => createAvatarInputRef.current?.click()}
              loading={avatarUploading}
              disabled={avatarUploading}
            >
              {t('settings.characters.aiAvatarChoose')}
            </Button>
            {createDraft.avatar && (
              <>
                <Text fontSize="xs" color="whiteAlpha.700">{createDraft.avatar}</Text>
                <Button
                  size="xs"
                  variant="ghost"
                  disabled={avatarUploading}
                  onClick={() => setCreateDraft((d) => (d ? { ...d, avatar: '' } : d))}
                >
                  {t('settings.characters.aiAvatarClear')}
                </Button>
              </>
            )}
          </HStack>
          {avatarUploadError && (
            <Text fontSize="xs" color="red.300">{avatarUploadError}</Text>
          )}
        </Field>

        {createError && (
          <Text fontSize="sm" color="red.300">{createError}</Text>
        )}

        <HStack>
          <Button
            tone="blue"
            onClick={handleCreate}
            loading={creating}
            loadingText={t('settings.characters.saving')}
            disabled={creating || avatarUploading}
          >
            {t('settings.characters.save')}
          </Button>
          <Button variant="outline" onClick={closeCreateForm} disabled={creating}>
            {t('common.cancel')}
          </Button>
        </HStack>
      </Stack>
    );
  }

  if (selectedRecord && draft) {
    return (
      <Stack {...settingStyles.common.container} maxW="none">
        <Heading size="sm">{t('settings.characters.editTitle')}</Heading>

        {selectedRecord.is_base && (
          <Text fontSize="xs" color="yellow.300">
            {t('settings.characters.editBaseNote')}
          </Text>
        )}

        <InputField
          label={t('settings.characters.name')}
          value={draft.conf_name}
          onChange={(value) => setDraft((d) => (d ? { ...d, conf_name: value } : d))}
          placeholder={t('settings.characters.namePlaceholder')}
        />

        <TextareaField
          label={t('settings.characters.persona')}
          help={t('settings.characters.personaHelp')}
          rows={8}
          placeholder={t('settings.characters.personaPlaceholder')}
          value={draft.persona_prompt}
          onChange={(value) => setDraft((d) => (d ? { ...d, persona_prompt: value } : d))}
        />

        {skinsLoading ? (
          <Text fontSize="xs" color="whiteAlpha.600">{t('settings.characters.loadingOptions')}</Text>
        ) : skinsError ? (
          <Text fontSize="xs" color="red.300">{t('settings.characters.errLoadFailed')}</Text>
        ) : skins.length === 0 ? (
          <Text fontSize="xs" color="whiteAlpha.600">{t('settings.characters.noSkinsHint')}</Text>
        ) : (
          <SelectField
            label={t('settings.characters.skin')}
            value={draft.live2d_model_name ? [draft.live2d_model_name] : []}
            onChange={(value) => setDraft((d) => (d ? { ...d, live2d_model_name: value[0] ?? '' } : d))}
            collection={skinCollection}
            placeholder={t('settings.characters.skin')}
          />
        )}

        <Stack gap={2}>
          <SelectField
            label={t('settings.characters.voice')}
            value={[draft.voice]}
            onChange={(value) => setDraft((d) => (d ? { ...d, voice: value[0] ?? INHERIT_VOICE } : d))}
            collection={voiceCollection}
            placeholder={t('settings.characters.voice')}
          />
          <Text fontSize="xs" color="whiteAlpha.600">
            {t('settings.characters.voiceHelp')}
          </Text>
          <Text fontSize="xs" color="whiteAlpha.500">
            {t('settings.characters.voiceEngineNote')}
          </Text>
          <HStack>
            <Button
              size="xs"
              variant="outline"
              disabled={!draft.voice || draft.voice === INHERIT_VOICE}
              loading={previewingVoice === draft.voice}
              onClick={() => handlePreview(draft.voice)}
            >
              {previewingVoice === draft.voice
                ? t('settings.characters.previewing')
                : t('settings.characters.preview')}
            </Button>
            {!voicesAreFull && (
              <Button
                size="xs"
                variant="ghost"
                onClick={handleShowAllVoices}
                loading={loadingFullVoices}
                disabled={voicesLoading}
              >
                {t('settings.characters.showAllVoices')}
              </Button>
            )}
            {voicesLoading && (
              <Text fontSize="xs" color="whiteAlpha.600">{t('settings.characters.loadingOptions')}</Text>
            )}
          </HStack>
          {voicesError && (
            <Text fontSize="xs" color="red.300">{t('settings.characters.errLoadFailed')}</Text>
          )}
          {previewError && (
            <Text fontSize="xs" color="red.300">{previewError}</Text>
          )}
        </Stack>

        {/* 兩個語言欄位放在語音區塊之後：回覆語言決定她「用什麼語言寫」，發聲
            語言決定「用什麼語言唸」。兩者不同時後端會在合成前先翻譯一次，那是
            延遲的主要來源之一，所以文案要講清楚這件事。 */}
        <InputField
          label={t('settings.characters.replyLanguage')}
          value={draft.reply_language}
          onChange={(value) => setDraft((d) => (d ? { ...d, reply_language: value } : d))}
          placeholder={t('settings.characters.replyLanguagePlaceholder')}
          help={t('settings.characters.replyLanguageHelp')}
        />

        {ttsModels.length > 0 && (
          <Stack gap={2}>
            <SelectField
              label={t('settings.characters.ttsEngine')}
              value={[draft.tts_model]}
              onChange={(value) => setDraft((d) => (
                d ? { ...d, tts_model: value[0] ?? INHERIT_ENGINE } : d
              ))}
              collection={engineCollection}
              placeholder={t('settings.characters.ttsEngine')}
            />
            <Text fontSize="xs" color="whiteAlpha.600">
              {t('settings.characters.ttsEngineHelp')}
            </Text>
          </Stack>
        )}

        {voiceLangs.length > 0 && (
          <Stack gap={2}>
            <SelectField
              label={t('settings.characters.voiceLang')}
              value={[draft.voice_lang]}
              onChange={(value) => setDraft((d) => (
                d ? { ...d, voice_lang: value[0] ?? INHERIT_LANG } : d
              ))}
              collection={voiceLangCollection}
              placeholder={t('settings.characters.voiceLang')}
            />
            <Text fontSize="xs" color="whiteAlpha.600">
              {t('settings.characters.voiceLangHelp')}
            </Text>
          </Stack>
        )}

        {/* 「用誰的聲音」——只對 GPT-SoVITS 有意義。三者是一組：聲線由參考音決定，
            逐字稿要跟那段音檔對得上，否則克隆出來的音色會歪。 */}
        <Stack gap={2}>
          <SelectField
            label={t('settings.characters.refAudioPath')}
            value={[draft.ref_audio_path || INHERIT_VOICE]}
            onChange={(value) => setDraft((d) => {
              if (!d) return d;
              const picked = value[0] === INHERIT_VOICE ? '' : (value[0] ?? '');
              // 換了參考音就換逐字稿。挑不到（手寫路徑、或沒有 sidecar）就維持原值，
              // 不要拿空字串把使用者自己打的逐字稿洗掉。
              const transcript = promptTextFor(picked);
              return {
                ...d,
                ref_audio_path: picked,
                prompt_text: transcript || d.prompt_text,
              };
            })}
            collection={refAudioCollection}
            placeholder={t('settings.characters.refAudioPath')}
          />
          <Text fontSize="xs" color="whiteAlpha.600">
            {t('settings.characters.refAudioPathHelp')}
          </Text>
        </Stack>

        <InputField
          label={t('settings.characters.promptText')}
          value={draft.prompt_text}
          onChange={(value) => setDraft((d) => (d ? { ...d, prompt_text: value } : d))}
          placeholder={t('settings.characters.promptTextPlaceholder')}
          help={t('settings.characters.promptTextHelp')}
        />

        {voiceLangs.length > 0 && (
          <Stack gap={2}>
            <SelectField
              label={t('settings.characters.promptLang')}
              value={[draft.prompt_lang]}
              onChange={(value) => setDraft((d) => (
                d ? { ...d, prompt_lang: value[0] ?? INHERIT_LANG } : d
              ))}
              collection={promptLangCollection}
              placeholder={t('settings.characters.promptLang')}
            />
            <Text fontSize="xs" color="whiteAlpha.600">
              {t('settings.characters.promptLangHelp')}
            </Text>
          </Stack>
        )}

        <InputField
          label={t('settings.characters.aiName')}
          value={draft.character_name}
          onChange={(value) => setDraft((d) => (d ? { ...d, character_name: value } : d))}
          help={t('settings.characters.aiNameHelp')}
        />

        <Field
          label={t('settings.characters.aiAvatar')}
          help={t('settings.characters.aiAvatarHelp')}
        >
          <HStack>
            <input
              ref={editAvatarInputRef}
              type="file"
              accept="image/*"
              style={{ display: 'none' }}
              onChange={(e) => {
                const file = e.target.files?.[0];
                e.target.value = '';
                if (file) handleEditAvatarFile(file);
              }}
            />
            <Button
              size="xs"
              variant="outline"
              onClick={() => editAvatarInputRef.current?.click()}
              loading={avatarUploading}
              disabled={avatarUploading}
            >
              {t('settings.characters.aiAvatarChoose')}
            </Button>
            {draft.avatar && (
              <>
                <Text fontSize="xs" color="whiteAlpha.700">{draft.avatar}</Text>
                <Button
                  size="xs"
                  variant="ghost"
                  disabled={avatarUploading}
                  onClick={() => setDraft((d) => (d ? { ...d, avatar: '' } : d))}
                >
                  {t('settings.characters.aiAvatarClear')}
                </Button>
              </>
            )}
          </HStack>
          {avatarUploadError && (
            <Text fontSize="xs" color="red.300">{avatarUploadError}</Text>
          )}
        </Field>

        {saveError && (
          <Text fontSize="sm" color="red.300">{saveError}</Text>
        )}

        <HStack>
          <Button
            tone="blue"
            onClick={handleSave}
            loading={saving}
            loadingText={t('settings.characters.saving')}
            disabled={saving || avatarUploading}
          >
            {t('settings.characters.save')}
          </Button>
          <Button variant="outline" onClick={closeEdit} disabled={saving}>
            {t('common.cancel')}
          </Button>
        </HStack>
      </Stack>
    );
  }

  return (
    <Stack {...settingStyles.common.container} maxW="none">
      <Stack
        direction={{ base: 'column', md: 'row' }}
        align={{ base: 'stretch', md: 'center' }}
        justify="space-between"
        gap={3}
      >
        <Text fontSize="sm" color="whiteAlpha.700">
          {t('settings.characters.description')}
        </Text>
        <HStack flexWrap="wrap">
          <Button size="xs" tone="blue" variant="outline" onClick={openCreate}>
            {t('settings.characters.add')}
          </Button>
          <Button size="xs" variant="ghost" onClick={() => setRefreshTick((n) => n + 1)}>
            {t('settings.characters.refresh')}
          </Button>
        </HStack>
      </Stack>

      <Text fontSize="xs" color="whiteAlpha.500">
        {t('settings.characters.memoryNote')}
      </Text>

      {listError && (
        <Text fontSize="sm" color="red.300">{listError}</Text>
      )}

      {characters.map((record) => (
        <Box
          key={record.filename}
          p={3}
          borderWidth="1px"
          borderColor="whiteAlpha.200"
          borderRadius="md"
        >
          <Stack
            direction={{ base: 'column', md: 'row' }}
            align={{ base: 'stretch', md: 'center' }}
            justify="space-between"
            gap={3}
          >
            <HStack flexWrap="wrap">
              <Text fontWeight="semibold">{record.conf_name || record.filename}</Text>
              {record.is_base && (
                <Text fontSize="xs" color="whiteAlpha.600">
                  {t('settings.characters.baseBadge')}
                </Text>
              )}
              {record.conf_name === confName && (
                <Text fontSize="xs" color="green.300">
                  {t('settings.characters.activeBadge')}
                </Text>
              )}
            </HStack>
            <HStack flexWrap="wrap">
              {/* 這個分頁的說明寫著「建立、編輯、切換」，但切換以前只存在於
                  「一般」分頁一個叫「角色預設」的下拉選單裡——名字不一樣、
                  位置也不一樣，站在這裡的人找不到它。切換的動作屬於這張清單。 */}
              {record.conf_name !== confName && (
                <Button
                  size="xs"
                  tone="blue"
                  onClick={() => switchCharacter(record.filename)}
                >
                  {t('settings.characters.use')}
                </Button>
              )}
              <Button size="xs" variant="outline" onClick={() => openEdit(record)}>
                {t('settings.characters.edit')}
              </Button>
              {!record.is_base && (
                <Button
                  size="xs"
                  tone="red"
                  variant="outline"
                  onClick={() => setPendingDeleteFilename(record.filename)}
                >
                  {t('settings.characters.delete')}
                </Button>
              )}
            </HStack>
          </Stack>

          {pendingDeleteFilename === record.filename && (
            <Box mt={2} p={2} borderWidth="1px" borderColor="red.700" borderRadius="sm">
              <Text fontSize="sm">
                {t('settings.characters.confirmDelete', {
                  name: record.conf_name || record.filename,
                })}
              </Text>
              <Text fontSize="xs" color="whiteAlpha.600">
                {t('settings.characters.deleteKeepsMemory')}
              </Text>
              {deleteError && (
                <Text fontSize="xs" color="red.300">{deleteError}</Text>
              )}
              <HStack mt={2}>
                <Button
                  size="xs"
                  tone="red"
                  onClick={() => handleDelete(record.filename)}
                  loading={deleting}
                >
                  {t('settings.characters.confirm')}
                </Button>
                <Button
                  size="xs"
                  variant="ghost"
                  onClick={() => setPendingDeleteFilename(null)}
                  disabled={deleting}
                >
                  {t('common.cancel')}
                </Button>
              </HStack>
            </Box>
          )}
        </Box>
      ))}
    </Stack>
  );
}

export default Characters;
