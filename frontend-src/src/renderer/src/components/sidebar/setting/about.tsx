import { 
  Box, 
  Stack, 
  Text, 
  Heading, 
  HStack,
  Icon,
} from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import { FaGithub, FaBook } from 'react-icons/fa';
import { settingStyles } from './setting-styles';
import { Button } from '@/components/ui/tw/primitives';

function About(): JSX.Element {
  const { t } = useTranslation();
  
  const openExternalLink = (url: string) => {
    // Handle external link opening via electron
    window.open(url, '_blank');
  };
  
  // 寫死的話，改了 package.json 這裡不會跟著動——一個安靜地慢慢變錯的數字。
  // __APP_VERSION__ 由 vite.config.ts 的 define 在建置時填入 package.json 的值。
  const appVersion = __APP_VERSION__;
  // const appAuthor = 'Tomoshibi';

  return (
    <Stack {...settingStyles.common.container} gap={3}>
      <Heading size="md" mb={1}>
        {t("settings.about.title")}
      </Heading>
      <Box>
        <Text fontWeight="bold" mb={0}>
          {t("settings.about.version")}
        </Text>
        <Text>{appVersion}</Text>
      </Box>
      {/* <Box mt={1}>
        <Text fontWeight="bold" mb={0}>{t('Author')}</Text>
        <Text>{appAuthor}</Text>
      </Box> */}
      <Box borderTop="1px solid" borderColor="whiteAlpha.200" pt={2} mt={1} />
      <Box mt={1}>
        <Text fontWeight="bold" mb={1}>
          {t("settings.about.projectLinks")}
        </Text>
        <HStack mt={1} gap={2} flexWrap="wrap">
          <Button
            size="sm"
            onClick={() =>
              openExternalLink(
                "https://github.com/weryk153/tomoshibi"
              )
            }
          >
            <Icon as={FaGithub} mr={2} /> {t("settings.about.github")}
          </Button>
          <Button
            size="sm"
            onClick={() => openExternalLink("https://docs.llmvtuber.com")}
          >
            <Icon as={FaBook} mr={2} /> {t("settings.about.documentation")}
          </Button>
        </HStack>
      </Box>
      <Box borderTop="1px solid" borderColor="whiteAlpha.200" pt={2} mt={1} />
      <Box mt={1}>
        <Button size="xs" tone="blue" onClick={() => openExternalLink("https://github.com/weryk153/tomoshibi/blob/main/LICENSE")}>
          {t("settings.about.viewLicense")}
        </Button>
      </Box>
      <Box mt={1}>
        <Text fontWeight="bold" mb={0}>
          {t("settings.about.copyright")}
        </Text>
        <Text>© {new Date().getFullYear()} Tomoshibi</Text>
      </Box>
    </Stack>
  );
}

export default About;
