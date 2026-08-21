/* eslint-disable import/no-extraneous-dependencies */
import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import LanguageDetector from "i18next-browser-languagedetector";

// Import translation resources
import zhTranslation from "./locales/zh/translation.json";
import enTranslation from "./locales/en/translation.json";
import jaTranslation from "./locales/ja/translation.json";
import koTranslation from "./locales/ko/translation.json";
import zhCNTranslation from "./locales/zh-CN/translation.json";

// Configure i18next instance
i18n
  // Detect user language
  .use(LanguageDetector)
  // Pass the i18n instance to react-i18next
  .use(initReactI18next)
  // Initialize i18next
  .init({
    // 預設繁體中文——主要使用者是繁中讀者
    fallbackLng: "zh",
    supportedLngs: ["zh", "en", "ja", "ko", "zh-CN"],
    nonExplicitSupportedLngs: true,
    // Debug mode for development
    debug: process.env.NODE_ENV === "development",
    // Namespaces configuration
    defaultNS: "translation",
    ns: ["translation"],
    // Resources containing translations
    resources: {
      zh: { translation: zhTranslation },
      en: { translation: enTranslation },
      ja: { translation: jaTranslation },
      ko: { translation: koTranslation },
      "zh-CN": { translation: zhCNTranslation },
    },
    // Language detection options
    detection: {
      // 只認 localStorage：不要用瀏覽器語言自動偵測，否則使用者在設定裡
      // 選過的語言會被系統語言蓋掉
      order: ["localStorage"],
      caches: ["localStorage"],
      htmlTag: document.documentElement,
    },
    // Escaping special characters
    interpolation: {
      escapeValue: false, // React already safes from XSS
    },
    // React config
    react: {
      useSuspense: true,
    },
  });

// Save language change to localStorage
i18n.on("languageChanged", (lng) => {
  localStorage.setItem("i18nextLng", lng);
  // Update HTML document lang attribute
  document.documentElement.lang = lng;
});

export default i18n;
