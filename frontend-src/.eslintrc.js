// airbnb 以前寫在 extends 裡，但套件從沒裝過，lint 一執行就失敗——等於從來沒有
// lint。留下會抓 bug 的規則（hooks 的呼叫順序曾讓整個 app 白屏），不把 airbnb 的
// 風格規則補回來：那幾千條從沒被執行過。
module.exports = {
  parser: '@typescript-eslint/parser',
  extends: [
    'eslint:recommended',
    'plugin:@typescript-eslint/recommended',
    'plugin:react/recommended',
    'plugin:react-hooks/recommended',
  ],
  plugins: ['@typescript-eslint', 'react', 'react-hooks'],
  settings: {
    react: { version: 'detect' },
  },
  env: { browser: true, es2022: true },
  parserOptions: { ecmaVersion: 'latest', sourceType: 'module' },
  overrides: [
    {
      files: ['*.js', '*.cjs', '*.mjs', 'scripts/**', 'src/main/**', 'src/preload/**'],
      env: { node: true },
    },
    {
      files: ['*.cjs'],
      rules: { '@typescript-eslint/no-var-requires': 'off' },
    },
  ],
  rules: {
    'no-unused-vars': 'off',
    'max-len': 'off',
    '@typescript-eslint/no-explicit-any': 'off',
    '@typescript-eslint/no-unused-vars': 'off',
    'no-console': 'off',
    'react/jsx-filename-extension': [1, { extensions: ['.tsx', '.jsx'] }],
    'react/react-in-jsx-scope': 'off',
    'react/jsx-props-no-spreading': 'off',
    quotes: 'off',
    'operator-linebreak': 'off',
    'react/display-name': 'off',
    'react-hooks/exhaustive-deps': 'off',
    'consistent-return': 'off',
    'object-curly-newline': 'off',
    'react/require-default-props': 'off',
    // 格式交給 prettier：沒有分號的檔案裡，`;(` 開頭是刻意的。
    'no-extra-semi': 'off',
    // 註解裡會寫全形空白當例子（說明它怎麼被處理）。
    'no-irregular-whitespace': ['error', { skipComments: true }],
  },
};
