import { create } from "zustand";

export interface LLMConfig {
  provider: string;
  baseUrl: string;
  apiKey: string;
  model: string;
  maxTokens: number;
  temperature: number;
}

export interface IMConfig {
  channelType: string;
  token: string;
  webhookUrl?: string;
  secret?: string;
}

export interface WorkspaceConfig {
  path: string;
  name: string;
  createNew: boolean;
}

export interface SetupConfig {
  // 快速配置
  llm: LLMConfig;
  im: IMConfig | null;

  // 完整向导
  workspace: WorkspaceConfig;
  pythonPath: string;
  installDeps: boolean;
  selectedSkills: string[];

  // 状态
  currentStep: number;
  mode: "quick" | "full" | null;
}

interface SetupConfigState extends SetupConfig {
  // Actions
  setLLMConfig: (config: Partial<LLMConfig>) => void;
  setIMConfig: (config: Partial<IMConfig> | null) => void;
  setWorkspaceConfig: (config: Partial<WorkspaceConfig>) => void;
  setPythonPath: (path: string) => void;
  setInstallDeps: (install: boolean) => void;
  setSelectedSkills: (skills: string[]) => void;
  setCurrentStep: (step: number) => void;
  setMode: (mode: "quick" | "full") => void;
  resetConfig: () => void;
}

const getDefaultLLMConfig = (): LLMConfig => ({
  provider: "dashscope",
  baseUrl: "https://dashscope.aliyuncs.com/compatible-mode/v1",
  apiKey: "",
  model: "qwen3.5-plus",
  maxTokens: 4096,
  temperature: 0.7,
});

const getDefaultWorkspaceConfig = (): WorkspaceConfig => ({
  path: "",
  name: "default",
  createNew: true,
});

export const useSetupConfigStore = create<SetupConfigState>((set) => ({
  // Default state
  llm: getDefaultLLMConfig(),
  im: null,
  workspace: getDefaultWorkspaceConfig(),
  pythonPath: "",
  installDeps: true,
  selectedSkills: [],
  currentStep: 1,
  mode: null,

  // Actions
  setLLMConfig: (config) =>
    set((state) => ({
      llm: { ...state.llm, ...config },
    })),

  setIMConfig: (config) =>
    set((state) => ({
      im: config !== null ? { ...state.im, ...config } as IMConfig : null,
    })),

  setWorkspaceConfig: (config) =>
    set((state) => ({
      workspace: { ...state.workspace, ...config },
    })),

  setPythonPath: (path) =>
    set(() => ({
      pythonPath: path,
    })),

  setInstallDeps: (install) =>
    set(() => ({
      installDeps: install,
    })),

  setSelectedSkills: (skills) =>
    set(() => ({
      selectedSkills: skills,
    })),

  setCurrentStep: (step) =>
    set(() => ({
      currentStep: step,
    })),

  setMode: (mode) =>
    set(() => ({
      mode,
      currentStep: 1,
    })),

  resetConfig: () =>
    set({
      llm: getDefaultLLMConfig(),
      im: null,
      workspace: getDefaultWorkspaceConfig(),
      pythonPath: "",
      installDeps: true,
      selectedSkills: [],
      currentStep: 1,
      mode: null,
    }),
}));
