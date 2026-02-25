import { useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { Brain, CheckCircle, ChevronRight, Play, Settings, Zap } from "lucide-react";
import { useAppStore } from "../../stores/appStore";
import { useSetupConfigStore } from "../../stores/setupConfigStore";
import { LLMSetupForm } from "./LLMSetupForm";
import { IMSetupForm } from "./IMSetupForm";
import { AutoConfigStep } from "./AutoConfigStep";

export type SetupMode = "quick" | "full";

export type SetupStep = {
  id: number;
  title: string;
  description: string;
  icon: React.ReactNode;
  completed: boolean;
};

interface SetupWizardProps {
  onComplete: () => void;
}

// StepContent 组件的 Props 类型
interface StepContentProps {
  step: number;
  mode: SetupMode;
  t: ReturnType<typeof useTranslation>["t"];
  onComplete: (success: boolean) => void;
}

/**
 * 配置向导 - 提供快速配置 (3 步) 和完整向导 (8 步) 两种模式
 */
export function SetupWizard({ onComplete }: SetupWizardProps) {
  const { t } = useTranslation();
  const [mode, setMode] = useState<SetupMode | null>(null);
  const [currentStep, setCurrentStep] = useState(1);
  const setSetupCompleted = useAppStore((s) => s.setSetupCompleted);
  const setupConfig = useSetupConfigStore();

  // 快速配置步骤 (3 步)
  const quickSteps: SetupStep[] = [
    {
      id: 1,
      title: t("setup.quick.step1Title", "添加 LLM 端点"),
      description: t("setup.quick.step1Desc", "配置语言模型提供商和 API Key"),
      icon: <Brain className="w-6 h-6" />,
      completed: false,
    },
    {
      id: 2,
      title: t("setup.quick.step2Title", "添加 IM 通道"),
      description: t("setup.quick.step2Desc", "可选配置 IM 机器人接入"),
      icon: <Settings className="w-6 h-6" />,
      completed: false,
    },
    {
      id: 3,
      title: t("setup.quick.step3Title", "一键自动配置"),
      description: t("setup.quick.step3Desc", "自动创建工作区、安装依赖、写入配置"),
      icon: <Zap className="w-6 h-6" />,
      completed: false,
    },
  ];

  // 完整向导步骤 (8 步)
  const fullSteps: SetupStep[] = [
    {
      id: 1,
      title: t("setup.full.step1Title", "开始"),
      description: t("setup.full.step1Desc", "欢迎与环境检查"),
      icon: <Play className="w-6 h-6" />,
      completed: false,
    },
    {
      id: 2,
      title: t("setup.full.step2Title", "工作区"),
      description: t("setup.full.step2Desc", "创建或选择工作区"),
      icon: <Brain className="w-6 h-6" />,
      completed: false,
    },
    {
      id: 3,
      title: t("setup.full.step3Title", "Python"),
      description: t("setup.full.step3Desc", "安装或选择 Python"),
      icon: <Settings className="w-6 h-6" />,
      completed: false,
    },
    {
      id: 4,
      title: t("setup.full.step4Title", "安装"),
      description: t("setup.full.step4Desc", "安装依赖"),
      icon: <Zap className="w-6 h-6" />,
      completed: false,
    },
    {
      id: 5,
      title: t("setup.full.step5Title", "LLM 端点"),
      description: t("setup.full.step5Desc", "配置 LLM 服务商"),
      icon: <Brain className="w-6 h-6" />,
      completed: false,
    },
    {
      id: 6,
      title: t("setup.full.step6Title", "IM 通道"),
      description: t("setup.full.step6Desc", "配置 IM 机器人"),
      icon: <Settings className="w-6 h-6" />,
      completed: false,
    },
    {
      id: 7,
      title: t("setup.full.step7Title", "工具与技能"),
      description: t("setup.full.step7Desc", "选择技能和工具"),
      icon: <CheckCircle className="w-6 h-6" />,
      completed: false,
    },
    {
      id: 8,
      title: t("setup.full.step8Title", "完成"),
      description: t("setup.full.step8Desc", "启动服务"),
      icon: <CheckCircle className="w-6 h-6" />,
      completed: false,
    },
  ];

  const steps = mode === "quick" ? quickSteps : fullSteps;
  const currentStepData = steps.find((s) => s.id === currentStep);

  const handleModeSelect = useCallback((selectedMode: SetupMode) => {
    setMode(selectedMode);
    setCurrentStep(1);
    setupConfig.setMode(selectedMode);
  }, [setupConfig]);

  const handleNext = useCallback(() => {
    if (currentStep < steps.length) {
      setCurrentStep((prev) => prev + 1);
      setupConfig.setCurrentStep(currentStep + 1);
    }
  }, [currentStep, steps.length, setupConfig]);

  const handleBack = useCallback(() => {
    if (currentStep > 1) {
      setCurrentStep((prev) => prev - 1);
      setupConfig.setCurrentStep(currentStep - 1);
    } else {
      setMode(null);
    }
  }, [currentStep, setupConfig]);

  const handleComplete = useCallback((success: boolean) => {
    if (success) {
      setSetupCompleted(true);
      onComplete();
    }
  }, [setSetupCompleted, onComplete]);

  // 模式选择页面
  if (!mode) {
    return (
      <div className="flex-1 flex items-center justify-center bg-bg-deep p-8">
        <div className="max-w-4xl w-full">
          <div className="text-center mb-8">
            <Brain className="w-16 h-16 text-accent mx-auto mb-4" />
            <h1 className="text-2xl font-bold font-code text-text-p mb-2">
              {t("setup.welcome", "欢迎使用 Coolaw DeskFlow")}
            </h1>
            <p className="text-text-m">
              {t("setup.selectMode", "选择配置模式开始使用")}
            </p>
          </div>

          <div className="grid md:grid-cols-2 gap-6">
            {/* 快速配置卡片 */}
            <div
              className="bg-bg p-6 rounded-2xl border border-surface cursor-pointer hover:border-accent transition-all duration-200 group"
              onClick={() => handleModeSelect("quick")}
            >
              <div className="flex items-center gap-4 mb-4">
                <div className="w-12 h-12 rounded-xl bg-accent/10 flex items-center justify-center group-hover:bg-accent/20 transition-colors">
                  <Zap className="w-6 h-6 text-accent" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-text-p">{t("setup.quick.title", "快速配置")}</h3>
                  <p className="text-sm text-text-m">{t("setup.quick.subtitle", "3 分钟快速上手")}</p>
                </div>
              </div>
              <ul className="space-y-2 text-sm text-text-s">
                <li className="flex items-center gap-2">
                  <CheckCircle className="w-4 h-4 text-accent" />
                  {t("setup.quick.feature1", "只需填写 API Key")}
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle className="w-4 h-4 text-accent" />
                  {t("setup.quick.feature2", "自动创建工作区")}
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle className="w-4 h-4 text-accent" />
                  {t("setup.quick.feature3", "自动安装依赖")}
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle className="w-4 h-4 text-accent" />
                  {t("setup.quick.feature4", "自动写入默认配置")}
                </li>
              </ul>
              <div className="mt-4 text-xs text-text-m">
                {t("setup.quick.recommend", "⭐ 推荐新手使用")}
              </div>
            </div>

            {/* 完整向导卡片 */}
            <div
              className="bg-bg p-6 rounded-2xl border border-surface cursor-pointer hover:border-accent transition-all duration-200 group"
              onClick={() => handleModeSelect("full")}
            >
              <div className="flex items-center gap-4 mb-4">
                <div className="w-12 h-12 rounded-xl bg-info/10 flex items-center justify-center group-hover:bg-info/20 transition-colors">
                  <Settings className="w-6 h-6 text-info" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-text-p">{t("setup.full.title", "完整向导")}</h3>
                  <p className="text-sm text-text-m">{t("setup.full.subtitle", "8 步精细控制")}</p>
                </div>
              </div>
              <ul className="space-y-2 text-sm text-text-s">
                <li className="flex items-center gap-2">
                  <CheckCircle className="w-4 h-4 text-info" />
                  {t("setup.full.feature1", "自定义工作区")}
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle className="w-4 h-4 text-info" />
                  {t("setup.full.feature2", "选择 Python 版本")}
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle className="w-4 h-4 text-info" />
                  {t("setup.full.feature3", "配置 MCP 工具")}
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle className="w-4 h-4 text-info" />
                  {t("setup.full.feature4", "调整人格角色")}
                </li>
              </ul>
              <div className="mt-4 text-xs text-text-m">
                {t("setup.full.recommend", "⭐ 高级用户使用")}
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // 步骤页面
  return (
    <div className="flex-1 flex bg-bg-deep">
      {/* 左侧步骤列表 */}
      <div className="w-72 bg-bg border-r border-surface p-6 overflow-y-auto">
        <div className="text-xs font-semibold text-text-m uppercase mb-4">
          {mode === "quick" ? t("setup.quick.title", "快速配置") : t("setup.full.title", "完整向导")}
        </div>
        <div className="space-y-2">
          {steps.map((step) => {
            const isActive = step.id === currentStep;
            const isCompleted = step.id < currentStep;
            return (
              <div
                key={step.id}
                className={`flex items-center gap-3 p-3 rounded-lg transition-all duration-200 ${
                  isActive
                    ? "bg-accent/10 border border-accent/30"
                    : isCompleted
                    ? "bg-surface-el border border-surface"
                    : "hover:bg-surface"
                }`}
              >
                <div
                  className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${
                    isCompleted
                      ? "bg-accent text-bg-deep"
                      : isActive
                      ? "bg-accent/20 text-accent"
                      : "bg-surface-el text-text-m"
                  }`}
                >
                  {isCompleted ? (
                    <CheckCircle className="w-4 h-4" />
                  ) : (
                    step.icon
                  )}
                </div>
                <div className="min-w-0 flex-1">
                  <div className={`text-sm truncate ${isActive ? "text-text-p font-medium" : "text-text-s"}`}>
                    {step.title}
                  </div>
                  {isActive && (
                    <div className="text-xs text-text-m truncate">{step.description}</div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* 右侧步骤内容 */}
      <div className="flex-1 flex flex-col">
        {/* 步骤内容区域 */}
        <div className="flex-1 p-8 overflow-y-auto">
          <div className="max-w-2xl mx-auto">
            <div className="flex items-center gap-3 mb-6">
              <div className="w-12 h-12 rounded-xl bg-accent/10 flex items-center justify-center">
                {currentStepData?.icon}
              </div>
              <div>
                <h2 className="text-xl font-bold text-text-p">{currentStepData?.title}</h2>
                <p className="text-sm text-text-m">{currentStepData?.description}</p>
              </div>
            </div>

            {/* 步骤内容 */}
            <StepContent
              step={currentStep}
              mode={mode}
              t={t}
              onComplete={handleComplete}
            />
          </div>
        </div>

        {/* 底部导航按钮 */}
        {!(mode === "quick" && currentStep === 3) && (
          <div className="border-t border-surface p-6 bg-bg">
            <div className="max-w-2xl mx-auto flex justify-between items-center">
              <button
                onClick={handleBack}
                className="px-4 py-2 rounded-lg border border-surface text-text-s hover:bg-surface hover:text-text-p transition-colors cursor-pointer"
              >
                {currentStep === 1 ? t("common.back", "返回") : t("common.previous", "上一步")}
              </button>
              <div className="text-sm text-text-m">
                {currentStep} / {steps.length}
              </div>
              {mode === "quick" && currentStep === 2 ? (
                <button
                  onClick={handleNext}
                  className="px-6 py-2 rounded-lg bg-accent text-bg-deep font-medium hover:bg-accent-hover transition-colors cursor-pointer flex items-center gap-2"
                >
                  {t("common.next", "下一步")}
                  <ChevronRight className="w-4 h-4" />
                </button>
              ) : mode === "full" && currentStep === 7 ? (
                <button
                  onClick={handleNext}
                  className="px-6 py-2 rounded-lg bg-accent text-bg-deep font-medium hover:bg-accent-hover transition-colors cursor-pointer flex items-center gap-2"
                >
                  {t("common.next", "下一步")}
                  <ChevronRight className="w-4 h-4" />
                </button>
              ) : (
                <div />
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// 步骤内容组件
function StepContent({ step, mode, t, onComplete }: StepContentProps) {
  if (mode === "quick") {
    return <QuickStepContent step={step} t={t} onComplete={onComplete} />;
  }
  return <FullStepContent step={step} t={t} onComplete={onComplete} />;
}

// 快速配置步骤内容
function QuickStepContent({ step, t, onComplete }: Omit<StepContentProps, "mode">) {
  switch (step) {
    case 1:
      return (
        <div className="space-y-4">
          <p className="text-text-s">{t("setup.quick.step1Content", "选择语言模型提供商并填写 API Key")}</p>
          <LLMSetupForm />
        </div>
      );
    case 2:
      return (
        <div className="space-y-4">
          <p className="text-text-s">{t("setup.quick.step2Content", "可选配置 IM 通道，稍后也可以在设置中配置")}</p>
          <IMSetupForm />
        </div>
      );
    case 3:
      return (
        <div className="space-y-4">
          <AutoConfigStep onComplete={onComplete} />
        </div>
      );
    default:
      return null;
  }
}

// 完整向导步骤内容
function FullStepContent({ step, t, onComplete }: Omit<StepContentProps, "mode">) {
  switch (step) {
    case 1:
      return (
        <div className="space-y-4">
          <p className="text-text-s">{t("setup.full.step1Content", "欢迎使用 Coolaw DeskFlow，开始配置您的 AI Agent")}</p>
          <div className="bg-surface rounded-xl p-4 border border-surface-el">
            <h4 className="text-sm font-medium text-text-p mb-2">{t("setup.full.envCheck", "环境检查")}</h4>
            <ul className="space-y-2 text-sm text-text-s">
              <li className="flex items-center gap-2">
                <CheckCircle className="w-4 h-4 text-accent" />
                {t("setup.full.checkOs", "操作系统：macOS")}
              </li>
              <li className="flex items-center gap-2">
                <CheckCircle className="w-4 h-4 text-accent" />
                {t("setup.full.checkHome", "家目录：可写")}
              </li>
            </ul>
          </div>
        </div>
      );
    case 2:
      return (
        <div className="space-y-4">
          <p className="text-text-s">{t("setup.full.step2Content", "创建工作区或选择已有工作区")}</p>
          <div className="bg-surface rounded-xl p-4 border border-surface-el">
            <p className="text-sm text-text-m">{t("setup.full.workspaceForm", "工作区表单占位")}</p>
          </div>
        </div>
      );
    case 3:
      return (
        <div className="space-y-4">
          <p className="text-text-s">{t("setup.full.step3Content", "安装 Python 或选择系统已安装的 Python")}</p>
          <div className="bg-surface rounded-xl p-4 border border-surface-el">
            <p className="text-sm text-text-m">{t("setup.full.pythonForm", "Python 选择表单占位")}</p>
          </div>
        </div>
      );
    case 4:
      return (
        <div className="space-y-4">
          <p className="text-text-s">{t("setup.full.step4Content", "安装项目依赖")}</p>
          <div className="bg-surface rounded-xl p-4 border border-surface-el">
            <p className="text-sm text-text-m">{t("setup.full.installDeps", "依赖安装占位")}</p>
          </div>
        </div>
      );
    case 5:
      return (
        <div className="space-y-4">
          <p className="text-text-s">{t("setup.full.step5Content", "配置 LLM 服务商")}</p>
          <LLMSetupForm />
        </div>
      );
    case 6:
      return (
        <div className="space-y-4">
          <p className="text-text-s">{t("setup.full.step6Content", "配置 IM 通道")}</p>
          <IMSetupForm />
        </div>
      );
    case 7:
      return (
        <div className="space-y-4">
          <p className="text-text-s">{t("setup.full.step7Content", "选择要安装的工具和技能")}</p>
          <div className="bg-surface rounded-xl p-4 border border-surface-el">
            <p className="text-sm text-text-m">{t("setup.full.skillsForm", "技能选择表单占位")}</p>
          </div>
        </div>
      );
    case 8:
      return (
        <div className="space-y-4">
          <AutoConfigStep onComplete={onComplete} />
        </div>
      );
    default:
      return null;
  }
}
