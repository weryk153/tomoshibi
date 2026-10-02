import {
  useCallback, useEffect, useState,
} from 'react';
import {
  Box, Heading, HStack, Stack, Text, Textarea,
} from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import { Button, TextInput } from '@/components/ui/tw/primitives';
import { Field } from '@/components/ui/tw/primitives';
import { toaster } from '@/components/ui/tw/toaster';
import { SaveStatus } from '@/components/ui/tw/save-status';
import { useAutosave } from '@/hooks/use-autosave';
import { useStream } from '@/context/stream-context';
import { useWebSocket } from '@/context/websocket-context';
import { useConfig } from '@/context/character-config-context';
import { wsService } from '@/services/websocket-service';
import { settingStyles } from './setting-styles';
import {
  createPersona,
  deletePersona,
  fetchPersonas,
  updatePersona,
  type PersonaDraft,
  type PersonaRecord,
} from '@/api/personas.ts';

const EMPTY_DRAFT: PersonaDraft = { name: '', prompt: '', id: '' };

function Personas(): JSX.Element {
  const { t } = useTranslation();
  const { baseUrl, sendMessage } = useWebSocket();
  const { confUid } = useConfig();
  const [personas, setPersonas] = useState<PersonaRecord[] | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [refreshTick, setRefreshTick] = useState(0);
  const [mode, setMode] = useState<'list' | 'create' | 'edit'>('list');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState<PersonaDraft>(EMPTY_DRAFT);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [applyingId, setApplyingId] = useState<string | null | undefined>(undefined);
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoadError(null);
    fetchPersonas(baseUrl, confUid).then((result) => {
      if (cancelled) return;
      if (result.ok) {
        setPersonas(result.data.personas);
        setActiveId(result.data.active_persona_id);
      } else {
        setPersonas([]);
        setLoadError(result.error);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [baseUrl, confUid, refreshTick]);

  useEffect(() => {
    const subscription = wsService.onMessage((message) => {
      // 被後端拒絕（例如直播中）也要停止轉圈，不然套用鍵永遠在載入中。
      if (message.type !== 'persona-switched' && message.type !== 'error') return;
      setApplyingId(undefined);
      setRefreshTick((value) => value + 1);
    });
    return () => subscription.unsubscribe();
  }, []);

  const closeForm = useCallback(() => {
    setMode('list');
    setEditingId(null);
    setDraft(EMPTY_DRAFT);
    setFormError(null);
  }, []);

  const openCreate = useCallback(() => {
    setMode('create');
    setEditingId(null);
    setDraft(EMPTY_DRAFT);
    setFormError(null);
  }, []);

  const openEdit = useCallback((persona: PersonaRecord) => {
    setMode('edit');
    setEditingId(persona.id);
    setDraft({ name: persona.name, prompt: persona.prompt, id: persona.id });
    setFormError(null);
  }, []);

  // 新增：按「建立」。
  const create = useCallback(async () => {
    setSaving(true);
    setFormError(null);
    const result = await createPersona(baseUrl, draft);
    setSaving(false);
    if (!result.ok) {
      setFormError(result.error);
      return;
    }
    toaster.create({
      title: t('settings.personas.created', { name: draft.name }),
      type: 'success',
      duration: 2200,
    });
    closeForm();
    setRefreshTick((value) => value + 1);
  }, [baseUrl, closeForm, draft, t]);

  // 編輯：改了就存；正在用的人設存好就重新套用，她立刻換成新的說法。
  const { live: streaming } = useStream();
  const editSaver = useAutosave(async (edit: { id: string; name: string; prompt: string }) => {
    const result = await updatePersona(baseUrl, edit.id, { name: edit.name, prompt: edit.prompt });
    if (!result.ok) return { ok: false, error: result.error } as const;
    // 直播中後端不准換人設（她正在對觀眾講話）：存了，但等直播結束再按「套用」。
    if (activeId === edit.id && !streaming) {
      setApplyingId(edit.id);
      sendMessage({ type: 'switch-persona', persona_id: edit.id });
    }
    setRefreshTick((value) => value + 1);
    return { ok: true } as const;
  });

  const changeDraft = useCallback((patch: Partial<typeof draft>) => {
    const next = { ...draft, ...patch };
    setDraft(next);
    if (mode === 'edit' && editingId) {
      editSaver.change({ id: editingId, name: next.name, prompt: next.prompt });
    }
  }, [draft, editSaver, editingId, mode]);

  const apply = useCallback((personaId: string | null) => {
    setApplyingId(personaId);
    sendMessage({ type: 'switch-persona', persona_id: personaId });
  }, [sendMessage]);

  const remove = useCallback(async (persona: PersonaRecord) => {
    const result = await deletePersona(baseUrl, persona.id);
    if (!result.ok) {
      setFormError(result.error);
      return;
    }
    toaster.create({
      title: t('settings.personas.deleted', { name: persona.name }),
      type: 'success',
      duration: 2200,
    });
    setPendingDelete(null);
    setRefreshTick((value) => value + 1);
  }, [baseUrl, t]);

  if (mode !== 'list') {
    return (
      <Stack {...settingStyles.common.container} maxW="none">
        <Heading size="sm">
          {t(mode === 'edit' ? 'settings.personas.editTitle' : 'settings.personas.addTitle')}
        </Heading>
        <Field label={t('settings.personas.name')}>
          <TextInput
            value={draft.name}
            placeholder={t('settings.personas.namePlaceholder')}
            onChange={(event) => changeDraft({ name: event.target.value })}
            onBlur={editSaver.flush}
          />
        </Field>
        <Field
          label={t('settings.personas.prompt')}
          help={t('settings.personas.promptHelp')}
        >
          <Textarea
            rows={12}
            value={draft.prompt}
            placeholder={t('settings.personas.promptPlaceholder')}
            onChange={(event) => changeDraft({ prompt: event.target.value })}
            onBlur={editSaver.flush}
          />
        </Field>
        {mode === 'create' && (
          <Field
            label={t('settings.personas.id')}
            help={t('settings.personas.idHelp')}
          >
            <TextInput
              value={draft.id || ''}
              placeholder="calm_companion"
              onChange={(event) => setDraft((current) => ({
                ...current,
                id: event.target.value,
              }))}
            />
          </Field>
        )}
        {formError && <Text color="red.300" fontSize="sm">{formError}</Text>}
        {mode === 'edit' && <SaveStatus state={editSaver.state} />}
        {mode === 'edit' && streaming && editingId === activeId && (
          <Text fontSize="xs" color="orange.300">{t('settings.personas.applyAfterStream')}</Text>
        )}
        <HStack>
          {mode === 'create' ? (
            <>
              <Button tone="blue" onClick={create} loading={saving}>
                {t('settings.personas.create')}
              </Button>
              <Button variant="outline" onClick={closeForm} disabled={saving}>
                {t('common.cancel')}
              </Button>
            </>
          ) : (
            // 改了就存；這顆只是回到清單（關掉前把還沒送的那筆送出去）。
            <Button variant="outline" onClick={() => { editSaver.flush(); closeForm(); }}>
              {t('common.close')}
            </Button>
          )}
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
          {t('settings.personas.description')}
        </Text>
        <Button size="xs" tone="blue" variant="outline" onClick={openCreate}>
          {t('settings.personas.add')}
        </Button>
      </Stack>
      <Text fontSize="xs" color="whiteAlpha.500">
        {t('settings.personas.independentNote')}
      </Text>

      <Box
        p={3}
        borderWidth="1px"
        borderColor={!activeId ? 'blue.400' : 'whiteAlpha.200'}
        borderRadius="md"
      >
        <HStack justify="space-between" flexWrap="wrap" gap={3}>
          <Stack gap={0}>
            <Text fontWeight="semibold">{t('settings.personas.characterDefault')}</Text>
            {!activeId && <Text fontSize="xs" color="blue.300">{t('settings.personas.active')}</Text>}
          </Stack>
          <Button
            size="xs"
            onClick={() => apply(null)}
            loading={applyingId === null}
            disabled={!activeId}
          >
            {t('settings.personas.apply')}
          </Button>
        </HStack>
      </Box>

      {personas === null && <Text>{t('settings.personas.loading')}</Text>}
      {loadError && <Text color="red.300" fontSize="sm">{loadError}</Text>}
      {formError && <Text color="red.300" fontSize="sm">{formError}</Text>}
      {(personas || []).map((persona) => (
        <Box
          key={persona.id}
          p={3}
          borderWidth="1px"
          borderColor={activeId === persona.id ? 'blue.400' : 'whiteAlpha.200'}
          borderRadius="md"
        >
          <Stack gap={2}>
            <Stack
              direction={{ base: 'column', md: 'row' }}
              align={{ base: 'stretch', md: 'center' }}
              justify="space-between"
              gap={3}
            >
              <Stack gap={0}>
                <Text fontWeight="semibold">{persona.name}</Text>
                <Text fontSize="xs" color="whiteAlpha.500">{persona.id}</Text>
                {activeId === persona.id && (
                  <Text fontSize="xs" color="blue.300">{t('settings.personas.active')}</Text>
                )}
              </Stack>
              <HStack flexWrap="wrap">
                <Button
                  size="xs"
                  tone="blue"
                  onClick={() => apply(persona.id)}
                  loading={applyingId === persona.id}
                  disabled={activeId === persona.id}
                >
                  {t('settings.personas.apply')}
                </Button>
                <Button size="xs" variant="outline" onClick={() => openEdit(persona)}>
                  {t('settings.personas.edit')}
                </Button>
              </HStack>
            </Stack>
            <Text fontSize="xs" color="whiteAlpha.600" whiteSpace="pre-wrap" lineClamp={4}>
              {persona.prompt}
            </Text>
            {pendingDelete === persona.id ? (
              <HStack flexWrap="wrap">
                <Text fontSize="xs" color="red.300">
                  {t('settings.personas.confirmDelete', { name: persona.name })}
                </Text>
                <Button size="xs" tone="red" onClick={() => remove(persona)}>
                  {t('settings.personas.confirm')}
                </Button>
                <Button size="xs" variant="ghost" onClick={() => setPendingDelete(null)}>
                  {t('common.cancel')}
                </Button>
              </HStack>
            ) : (
              <Button
                size="xs"
                variant="ghost"
                tone="red"
                className="self-start"
                onClick={() => setPendingDelete(persona.id)}
                disabled={activeId === persona.id}
              >
                {t('settings.personas.delete')}
              </Button>
            )}
          </Stack>
        </Box>
      ))}
      {personas?.length === 0 && (
        <Text fontSize="sm" color="whiteAlpha.600">{t('settings.personas.empty')}</Text>
      )}
    </Stack>
  );
}

export default Personas;
