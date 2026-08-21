// 群組管理抽屜。Ark Dialog + Tailwind（見 components/ui/tw/drawer.tsx）。
//
// 剪貼簿也一併換成 Ark 的 Clipboard：Chakra 的 ui/clipboard 包的就是它，換過來
// 之後「已複製」的狀態切換仍由同一顆狀態機處理，只是圖示與樣式改寫在這裡。

import { FiX, FiCopy, FiCheck } from 'react-icons/fi';
import { useTranslation } from 'react-i18next';
import { Clipboard as ArkClipboard } from '@ark-ui/react';
import { Drawer, DrawerCloseAction } from '@/components/ui/tw/drawer';
import { Button, cx } from '@/components/ui/tw/primitives';
import { useGroupDrawer } from '@/hooks/sidebar/use-group-drawer';
import { useGroup } from '@/context/group-context';

interface GroupDrawerProps {
  children: React.ReactNode;
}

const SECTION_TITLE = 'mb-3 text-lg font-semibold text-white';
const ROW = 'flex items-center justify-between gap-2 rounded-md bg-walpha-100 p-2';
const MEMBER_TEXT = 'text-sm text-white break-all';

function GroupDrawer({ children }: GroupDrawerProps) {
  const { t } = useTranslation();
  const { selfUid, sortedGroupMembers, isOwner } = useGroup();
  const {
    isOpen,
    setIsOpen,
    inviteUid,
    setInviteUid,
    handleInvite,
    handleRemove,
    handleLeaveGroup,
    requestGroupInfo,
  } = useGroupDrawer();

  return (
    <Drawer
      open={isOpen}
      onOpenChange={(open) => {
        setIsOpen(open);
        if (open) requestGroupInfo();
      }}
      placement="start"
      title={t('group.management')}
      trigger={children}
      footer={(
        <DrawerCloseAction>
          <Button variant="outline" tone="gray">{t('common.close')}</Button>
        </DrawerCloseAction>
      )}
    >
      <div className="flex-1 overflow-y-auto px-4 py-2">
        <section className="mb-6">
          <h3 className={SECTION_TITLE}>{t('group.yourUuid')}</h3>
          <div className={ROW}>
            <span className={MEMBER_TEXT}>{selfUid}</span>
            <ArkClipboard.Root value={selfUid}>
              <ArkClipboard.Control>
                <ArkClipboard.Trigger
                  className={cx(
                    'rounded p-1.5 text-white outline-none transition-colors',
                    'hover:bg-walpha-200 focus-visible:ring-2 focus-visible:ring-blue-500/40',
                  )}
                  aria-label={t('group.yourUuid')}
                >
                  {/* Indicator 依複製狀態切換內容，copied 之後由 zag 自己在
                      timeout 後切回來——不需要在這裡管計時器。 */}
                  <ArkClipboard.Indicator copied={<FiCheck className="text-green-400" />}>
                    <FiCopy />
                  </ArkClipboard.Indicator>
                </ArkClipboard.Trigger>
              </ArkClipboard.Control>
            </ArkClipboard.Root>
          </div>
        </section>

        <section className="mb-6">
          <h3 className={SECTION_TITLE}>{t('group.inviteMember')}</h3>
          <div className="flex gap-2">
            <input
              className={cx(
                'flex-1 rounded-md bg-walpha-100 px-3 py-2 text-sm text-white outline-none',
                'placeholder:text-walpha-400 transition-colors hover:bg-walpha-200',
                'focus-visible:ring-2 focus-visible:ring-blue-500/40',
              )}
              value={inviteUid}
              onChange={(e) => setInviteUid(e.target.value)}
              placeholder={t('group.enterMemberUuid')}
            />
            <Button variant="ghost" tone="gray" onClick={handleInvite}>
              {t('group.invite')}
            </Button>
          </div>
        </section>

        <section className="mb-6">
          <h3 className={SECTION_TITLE}>{t('group.members')}</h3>
          <div className="flex flex-col gap-2">
            {sortedGroupMembers.map((memberId) => {
              const isSelf = memberId === selfUid;
              const canAct = (isOwner && !isSelf) || (!isOwner && isSelf);
              const actionLabel = isSelf ? t('group.leaveGroup') : t('group.removeMember');
              return (
                <div key={memberId} className={ROW}>
                  <span className={MEMBER_TEXT}>
                    {isSelf ? `${memberId} (${t('group.you')})` : memberId}
                  </span>
                  {canAct && (
                    <Button
                      size="xs"
                      variant="ghost"
                      tone="red"
                      aria-label={actionLabel}
                      title={actionLabel}
                      onClick={() => (isSelf ? handleLeaveGroup(selfUid) : handleRemove(memberId))}
                    >
                      {isSelf ? t('group.leave') : <FiX />}
                    </Button>
                  )}
                </div>
              );
            })}
          </div>
        </section>
      </div>
    </Drawer>
  );
}

export default GroupDrawer;
