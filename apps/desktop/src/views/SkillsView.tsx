import { useEffect, useState, useCallback, useMemo } from "react";
import { useTranslation } from "react-i18next";
import {
  Globe,
  FolderOpen,
  Terminal,
  Code2,
  FileText,
  Shield,
  Search,
  Download,
  RefreshCw,
  CheckCircle,
  XCircle,
  Loader,
  SortAsc,
  SortDesc,
  Calendar,
} from "lucide-react";
import { useAppStore } from "../stores/appStore";

interface Skill {
  name: string;
  description: string;
  type: "system" | "user" | "auto-gen" | "utility" | "ai";
  version: string;
  is_active: boolean;
  icon: string;
  color: string;
  installed_at?: string;
}

const ICON_MAP: Record<string, React.ReactNode> = {
  globe: <Globe className="w-5 h-5" />,
  folder: <FolderOpen className="w-5 h-5" />,
  terminal: <Terminal className="w-5 h-5" />,
  code: <Code2 className="w-5 h-5" />,
  file: <FileText className="w-5 h-5" />,
  shield: <Shield className="w-5 h-5" />,
  search: <Search className="w-5 h-5" />,
  default: <FileText className="w-5 h-5" />,
};

const COLOR_MAP: Record<string, string> = {
  blue: "bg-blue-500/10 text-blue-400",
  green: "bg-green-500/10 text-green-400",
  amber: "bg-amber-500/10 text-amber-400",
  purple: "bg-purple-500/10 text-purple-400",
  cyan: "bg-cyan-500/10 text-cyan-400",
  rose: "bg-rose-500/10 text-rose-400",
  gray: "bg-gray-500/10 text-gray-400",
};

const TAG_COLOR: Record<string, string> = {
  system: "bg-blue-500/10 text-blue-400",
  user: "bg-purple-500/10 text-purple-400",
  "auto-gen": "bg-accent/10 text-accent",
  utility: "bg-cyan-500/10 text-cyan-400",
  ai: "bg-rose-500/10 text-rose-400",
};

type FilterType = "all" | "system" | "user" | "auto-gen" | "utility" | "ai";
type SortType = "name" | "installed_at";

/**
 * Skills management view with real-time data.
 */
export default function SkillsView() {
  const { t } = useTranslation();
  const serverUrl = useAppStore((s) => s.serverUrl);
  const [skills, setSkills] = useState<Skill[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<FilterType>("all");
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<SortType>("installed_at");
  const [sortDesc, setSortDesc] = useState(true);
  const [toggling, setToggling] = useState<string | null>(null);
  const [toast, setToast] = useState<{ message: string; success: boolean } | null>(null);

  const fetchSkills = useCallback(async () => {
    try {
      setLoading(true);
      const response = await fetch(`${serverUrl}/api/skills`);
      if (response.ok) {
        const data = await response.json();
        setSkills(data.skills || []);
      } else {
        setError(t("common.error"));
      }
    } catch (err) {
      setError(t("common.error"));
    } finally {
      setLoading(false);
    }
  }, [t, serverUrl]);

  useEffect(() => {
    fetchSkills();
  }, [fetchSkills]);

  const handleToggle = async (skillName: string, currentStatus: boolean) => {
    setToggling(skillName);
    try {
      const action = currentStatus ? "disable" : "enable";
      const response = await fetch(`${serverUrl}/api/skills/${skillName}/toggle?action=${action}`, {
        method: "POST",
      });
      const result = await response.json();

      if (result.success) {
        setSkills((prev) =>
          prev.map((s) =>
            s.name === skillName ? { ...s, is_active: result.is_active } : s
          )
        );
        setToast({
          message: t("skills.toggleSuccess", { action }),
          success: true,
        });
      } else {
        setToast({
          message: t("skills.toggleFailed", { action }),
          success: false,
        });
      }
    } catch (err) {
      setToast({
        message: t("skills.toggleFailed", { action: "toggle" }),
        success: false,
      });
    } finally {
      setToggling(null);
      setTimeout(() => setToast(null), 3000);
    }
  };

  const [installing, setInstalling] = useState<string | null>(null);
  const [showInstallModal, setShowInstallModal] = useState(false);
  const [installMethod, setInstallMethod] = useState<"template" | "github" | "upload">("template");
  const [selectedTemplate, setSelectedTemplate] = useState("");
  const [githubUrl, setGithubUrl] = useState("");
  const [installToast, setInstallToast] = useState<{ message: string; success: boolean } | null>(null);

  const handleInstall = () => {
    setShowInstallModal(true);
  };

  const handleInstallConfirm = async () => {
    setInstalling("installing");
    try {
      let payload: Record<string, string> = {};

      if (installMethod === "template") {
        if (!selectedTemplate) {
          setInstallToast({ message: t("skills.pleaseSelectTemplate"), success: false });
          setInstalling(null);
          return;
        }
        payload = { template_name: selectedTemplate };
      } else if (installMethod === "github") {
        if (!githubUrl) {
          setInstallToast({ message: t("skills.pleaseEnterGithubUrl"), success: false });
          setInstalling(null);
          return;
        }
        payload = { source_url: githubUrl };
      }

      const response = await fetch(`${serverUrl}/api/skills/install`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const result = await response.json();

      if (result.success) {
        setInstallToast({
          message: t("skills.installSuccess"),
          success: true,
        });
        setShowInstallModal(false);
        fetchSkills();
      } else {
        setInstallToast({
          message: t("skills.installFailed"),
          success: false,
        });
      }
    } catch (err) {
      setInstallToast({
        message: `${t("skills.installFailed")}: ${err}`,
        success: false,
      });
    } finally {
      setInstalling(null);
      setTimeout(() => setInstallToast(null), 5000);
    }
  };

  // Filter and sort skills
  const filteredSkills = useMemo(() => {
    let result = skills.filter((skill) => {
      const matchesFilter =
        filter === "all" ||
        skill.type.toLowerCase() === filter.toLowerCase() ||
        (filter === "auto-gen" && skill.type === "auto-gen");
      const matchesSearch =
        search === "" ||
        skill.name.toLowerCase().includes(search.toLowerCase()) ||
        skill.description.toLowerCase().includes(search.toLowerCase());
      return matchesFilter && matchesSearch;
    });

    // Sort
    result = [...result].sort((a, b) => {
      if (sort === "name") {
        return sortDesc ? b.name.localeCompare(a.name) : a.name.localeCompare(b.name);
      } else if (sort === "installed_at") {
        const aTime = a.installed_at ? new Date(a.installed_at).getTime() : 0;
        const bTime = b.installed_at ? new Date(b.installed_at).getTime() : 0;
        return sortDesc ? bTime - aTime : aTime - bTime;
      }
      return 0;
    });

    return result;
  }, [skills, filter, search, sort, sortDesc]);

  // Statistics
  const stats = useMemo(() => {
    const total = skills.length;
    const system = skills.filter((s) => s.type === "system").length;
    const user = skills.filter((s) => s.type === "user" || s.type === "utility" || s.type === "ai").length;
    const withInstallTime = skills.filter((s) => s.installed_at).length;
    return { total, system, user, withInstallTime };
  }, [skills]);

  const filterTabs = [
    { key: "all", label: t("skills.filters.all") },
    { key: "system", label: t("skills.filters.system") },
    { key: "user", label: t("skills.filters.user") },
    { key: "auto-gen", label: t("skills.filters.autoGen") },
  ];

  const formatDate = (isoString?: string) => {
    if (!isoString) return "-";
    try {
      const date = new Date(isoString);
      return date.toLocaleDateString("zh-CN", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
    } catch {
      return isoString;
    }
  };

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Header */}
      <div className="h-14 border-b border-surface flex items-center px-6 shrink-0">
        <h1 className="text-lg font-semibold font-code">{t("skills.title")}</h1>
        <div className="ml-6 flex items-center gap-2">
          {filterTabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setFilter(tab.key as FilterType)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium cursor-pointer transition-colors duration-200 ${
                tab.key === filter
                  ? "bg-accent/10 text-accent"
                  : "text-text-s hover:bg-surface"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <div className="ml-auto flex items-center gap-3">
          {/* Statistics */}
          <div className="flex items-center gap-4 px-3 py-1.5 bg-surface/50 rounded-lg border border-surface-el">
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-text-m">{t("skills.total")}</span>
              <span className="text-sm font-semibold text-accent">{stats.total}</span>
            </div>
            <div className="w-px h-4 bg-surface-el" />
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-text-m">{t("skills.filters.system")}</span>
              <span className="text-sm font-semibold text-blue-400">{stats.system}</span>
            </div>
            <div className="w-px h-4 bg-surface-el" />
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-text-m">{t("skills.filters.user")}</span>
              <span className="text-sm font-semibold text-purple-400">{stats.user}</span>
            </div>
          </div>

          {/* Sort */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => setSort(sort === "name" ? "installed_at" : "name")}
              className="px-3 py-1.5 rounded-lg text-xs text-text-s border border-surface-el hover:bg-surface cursor-pointer transition-colors duration-200 flex items-center gap-1.5"
              title={t("skills.sortTip")}
            >
              {sort === "name" ? (
                <>
                  <SortAsc className="w-3.5 h-3.5" />
                  {t("skills.sortByName")}
                </>
              ) : (
                <>
                  <Calendar className="w-3.5 h-3.5" />
                  {t("skills.sortByTime")}
                </>
              )}
            </button>
            <button
              onClick={() => setSortDesc(!sortDesc)}
              className="px-3 py-1.5 rounded-lg text-xs text-text-s border border-surface-el hover:bg-surface cursor-pointer transition-colors duration-200"
              title={sortDesc ? t("skills.sortAsc") : t("skills.sortDesc")}
            >
              {sortDesc ? <SortDesc className="w-3.5 h-3.5" /> : <SortAsc className="w-3.5 h-3.5" />}
            </button>
          </div>

          <div className="relative">
            <Search className="w-4 h-4 text-text-m absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={t("skills.search")}
              className="bg-bg-base border border-surface-el rounded-lg pl-9 pr-3 py-1.5 text-sm text-text-p placeholder:text-text-m focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/15 transition-all duration-200 w-48"
            />
          </div>
          <button
            onClick={fetchSkills}
            disabled={loading}
            className="px-3 py-1.5 rounded-lg text-sm text-text-s border border-surface-el hover:bg-surface cursor-pointer transition-colors duration-200 flex items-center gap-1.5 disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            {t("skills.refresh")}
          </button>
          <button
            onClick={handleInstall}
            className="px-3 py-1.5 rounded-lg bg-accent text-bg-deep text-sm font-medium flex items-center gap-1.5 cursor-pointer hover:bg-accent-hover transition-colors duration-200"
          >
            <Download className="w-4 h-4" />
            {t("skills.install")}
          </button>
        </div>
      </div>

      {/* Toast */}
      {toast && (
        <div className="absolute top-16 right-6 z-50">
          <div
            className={`px-4 py-3 rounded-lg border flex items-center gap-2 ${
              toast.success
                ? "bg-green-500/10 border-green-500/30 text-green-500"
                : "bg-red-500/10 border-red-500/30 text-red-500"
            }`}
          >
            {toast.success ? (
              <CheckCircle className="w-4 h-4" />
            ) : (
              <XCircle className="w-4 h-4" />
            )}
            <span className="text-sm">{toast.message}</span>
          </div>
        </div>
      )}

      {/* Grid */}
      <div className="flex-1 overflow-y-auto p-6">
        {loading ? (
          <div className="flex items-center justify-center h-64">
            <RefreshCw className="w-8 h-8 text-text-m animate-spin" />
          </div>
        ) : error ? (
          <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 text-red-500">
            {error}
          </div>
        ) : filteredSkills.length === 0 ? (
          <div className="text-center py-16">
            <div className="w-16 h-16 rounded-full bg-surface-el flex items-center justify-center mx-auto mb-4">
              <Search className="w-8 h-8 text-text-m" />
            </div>
            <h3 className="text-lg font-semibold text-text-s">{t("skills.noSkillsFound")}</h3>
            <p className="text-sm text-text-m mt-2">
              {search || filter !== "all"
                ? t("skills.adjustSearch")
                : t("skills.installToStart")}
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-3 gap-4 w-full max-w-7xl mx-auto pb-8">
            {filteredSkills.map((skill) => (
              <div
                key={skill.name}
                className="bg-surface border border-surface-el rounded-xl p-4 cursor-pointer hover:border-text-m transition-colors duration-200"
              >
                <div className="flex items-start justify-between">
                  <div
                    className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                      COLOR_MAP[skill.color] || COLOR_MAP.gray
                    }`}
                  >
                    {ICON_MAP[skill.icon] || ICON_MAP.default}
                  </div>
                  <button
                    onClick={() => handleToggle(skill.name, skill.is_active)}
                    disabled={toggling === skill.name}
                    className={`w-6 h-6 rounded-full flex items-center justify-center cursor-pointer transition-colors duration-200 ${
                      skill.is_active
                        ? "bg-accent/20 text-accent"
                        : "bg-text-m/20 text-text-m"
                    } hover:opacity-80 disabled:opacity-50`}
                    title={skill.is_active ? t("skills.clickToDisable") : t("skills.clickToEnable")}
                  >
                    {toggling === skill.name ? (
                      <RefreshCw className="w-3 h-3 animate-spin" />
                    ) : skill.is_active ? (
                      <CheckCircle className="w-3 h-3" />
                    ) : (
                      <XCircle className="w-3 h-3" />
                    )}
                  </button>
                </div>
                <h3 className="text-sm font-semibold font-code mt-3">{skill.name}</h3>
                <p className="text-xs text-text-s mt-1 leading-relaxed line-clamp-2">
                  {skill.description}
                </p>
                <div className="flex items-center gap-2 mt-3 flex-wrap">
                  <span
                    className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-code font-medium ${
                      TAG_COLOR[skill.type] || TAG_COLOR.user
                    }`}
                  >
                    {skill.type === "auto-gen"
                      ? t("skills.filters.autoGen")
                      : t(`skills.filters.${skill.type}`) || skill.type}
                  </span>
                  <span className="text-xs text-text-m">{skill.version}</span>
                  {skill.installed_at && (
                    <span className="text-xs text-text-m flex items-center gap-1 ml-auto">
                      <Calendar className="w-3 h-3" />
                      {formatDate(skill.installed_at)}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Install Modal */}
      {showInstallModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-surface border border-surface-el rounded-xl p-6 w-full max-w-md">
            <h2 className="text-lg font-semibold font-code mb-4">{t("skills.install")}</h2>

            {/* Install Method Tabs */}
            <div className="flex gap-2 mb-4">
              <button
                onClick={() => setInstallMethod("template")}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  installMethod === "template"
                    ? "bg-accent/10 text-accent"
                    : "bg-surface-el text-text-s"
                }`}
              >
                {t("skills.template")}
              </button>
              <button
                onClick={() => setInstallMethod("github")}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  installMethod === "github"
                    ? "bg-accent/10 text-accent"
                    : "bg-surface-el text-text-s"
                }`}
              >
                {t("skills.github")}
              </button>
            </div>

            {/* Template Selection */}
            {installMethod === "template" && (
              <div className="space-y-3">
                <p className="text-sm text-text-s">{t("skills.selectTemplate")}</p>
                <select
                  value={selectedTemplate}
                  onChange={(e) => setSelectedTemplate(e.target.value)}
                  className="w-full bg-bg-base border border-surface-el rounded-lg px-3 py-2 text-sm focus:border-accent focus:outline-none"
                >
                  <option value="">-- {t("skills.selectTemplate")} --</option>
                  <option value="document_processor">{t("skills.templates.documentProcessor")}</option>
                  <option value="code_runner">{t("skills.templates.codeRunner")}</option>
                  <option value="image_analyzer">{t("skills.templates.imageAnalyzer")}</option>
                </select>
              </div>
            )}

            {/* GitHub URL */}
            {installMethod === "github" && (
              <div className="space-y-3">
                <p className="text-sm text-text-s">{t("skills.enterGithubUrl")}</p>
                <input
                  type="text"
                  value={githubUrl}
                  onChange={(e) => setGithubUrl(e.target.value)}
                  placeholder={t("skills.githubUrlPlaceholder")}
                  className="w-full bg-bg-base border border-surface-el rounded-lg px-3 py-2 text-sm focus:border-accent focus:outline-none"
                />
              </div>
            )}

            {/* Action Buttons */}
            <div className="flex gap-3 mt-6 pt-4 border-t border-surface-el">
              <button
                onClick={() => setShowInstallModal(false)}
                className="flex-1 px-4 py-2 rounded-lg text-sm font-medium border border-surface-el hover:bg-surface transition-colors"
              >
                {t("common.cancel")}
              </button>
              <button
                onClick={handleInstallConfirm}
                disabled={installing === "installing"}
                className="flex-1 px-4 py-2 rounded-lg text-sm font-medium bg-accent text-bg-deep hover:bg-accent-hover transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                {installing === "installing" && <Loader className="w-4 h-4 animate-spin" />}
                {installing === "installing" ? t("skills.installing") : t("skills.install")}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Install Toast */}
      {installToast && (
        <div className="fixed top-16 right-6 z-50">
          <div
            className={`px-4 py-3 rounded-lg border flex items-center gap-2 ${
              installToast.success
                ? "bg-green-500/10 border-green-500/30 text-green-500"
                : "bg-red-500/10 border-red-500/30 text-red-500"
            }`}
          >
            {installToast.success ? (
              <CheckCircle className="w-4 h-4" />
            ) : (
              <XCircle className="w-4 h-4" />
            )}
            <span className="text-sm">{installToast.message}</span>
          </div>
        </div>
      )}
    </div>
  );
}
