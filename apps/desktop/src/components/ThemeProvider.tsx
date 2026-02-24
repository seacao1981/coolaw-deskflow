import { useEffect } from "react";
import { useThemeStore } from "../stores/themeStore";
import { useLocaleStore } from "../stores/localeStore";

interface ThemeProviderProps {
  children: React.ReactNode;
}

export function ThemeProvider({ children }: ThemeProviderProps) {
  const theme = useThemeStore((s) => s.theme);
  const locale = useLocaleStore((s) => s.locale);

  useEffect(() => {
    // Apply theme to document
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  useEffect(() => {
    // Apply locale to document
    document.documentElement.setAttribute("lang", locale);
  }, [locale]);

  return <>{children}</>;
}
