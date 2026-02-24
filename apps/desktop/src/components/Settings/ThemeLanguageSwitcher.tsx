import { useThemeStore } from "../../stores/themeStore";
import { useLocaleStore } from "../../stores/localeStore";
import { Sun, Moon, Languages } from "lucide-react";
import { useTranslation } from "react-i18next";

export function LocaleSwitcher() {
  const { locale, setLocale } = useLocaleStore();
  const { t } = useTranslation();

  return (
    <div className="flex items-center gap-2">
      <Languages className="w-4 h-4 text-text-s" />
      <select
        value={locale}
        onChange={(e) => setLocale(e.target.value as "zh-CN" | "en-US")}
        className="setting-input py-1.5 px-2 text-sm"
      >
        <option value="zh-CN">{t("settings.languageChinese")}</option>
        <option value="en-US">{t("settings.languageEnglish")}</option>
      </select>
    </div>
  );
}

export function ThemeSwitcher() {
  const { theme, toggleTheme } = useThemeStore();
  const { t } = useTranslation();

  return (
    <div className="flex items-center gap-2">
      {theme === "dark" ? (
        <Moon className="w-4 h-4 text-text-s" />
      ) : (
        <Sun className="w-4 h-4 text-text-s" />
      )}
      <button
        onClick={toggleTheme}
        className="setting-input py-1.5 px-3 text-sm flex items-center gap-2 cursor-pointer"
      >
        {theme === "dark" ? t("settings.themeDark") : t("settings.themeLight")}
      </button>
    </div>
  );
}
