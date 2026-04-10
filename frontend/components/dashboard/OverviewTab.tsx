interface OverviewTabProps {
  stats: {
    designs: number;
    materials: number;
    templates: number;
  };
  isLoading: boolean;
  onTabChange: (tab: 'upload' | 'generate' | 'history' | 'templates') => void;
}

export default function OverviewTab({ stats, isLoading, onTabChange }: OverviewTabProps) {
  const features = [
    {
      title: '上传素材',
      description: '上传设计灵感图片，AI 分析风格和图案类型',
      icon: '📤',
      tab: 'upload' as const,
      color: 'bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800',
      textColor: 'text-blue-900 dark:text-blue-100',
    },
    {
      title: '生成图案',
      description: '基于素材生成 AI 驱动的服装图案设计',
      icon: '✨',
      tab: 'generate' as const,
      color: 'bg-purple-50 dark:bg-purple-900/20 border-purple-200 dark:border-purple-800',
      textColor: 'text-purple-900 dark:text-purple-100',
    },
    {
      title: '设计历史',
      description: '查看所有设计项目和版本历史记录',
      icon: '📋',
      tab: 'history' as const,
      color: 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800',
      textColor: 'text-green-900 dark:text-green-100',
    },
    {
      title: '服装模板',
      description: '浏览可用的服装模板库',
      icon: '👔',
      tab: 'templates' as const,
      color: 'bg-orange-50 dark:bg-orange-900/20 border-orange-200 dark:border-orange-800',
      textColor: 'text-orange-900 dark:text-orange-100',
    },
  ];

  return (
    <div>
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-zinc-950 dark:text-zinc-50 mb-2">
          控制台
        </h2>
        <p className="text-zinc-600 dark:text-zinc-400">
          快速访问您的设计工具和项目
        </p>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-24 bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800 animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <div className="bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800 p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-zinc-500 dark:text-zinc-400">设计项目</p>
                <p className="text-3xl font-bold text-zinc-950 dark:text-zinc-50 mt-1">
                  {stats.designs}
                </p>
              </div>
              <div className="h-12 w-12 rounded-lg bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center">
                <span className="text-2xl">📐</span>
              </div>
            </div>
          </div>

          <div className="bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800 p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-zinc-500 dark:text-zinc-400">上传素材</p>
                <p className="text-3xl font-bold text-zinc-950 dark:text-zinc-50 mt-1">
                  {stats.materials}
                </p>
              </div>
              <div className="h-12 w-12 rounded-lg bg-purple-100 dark:bg-purple-900/30 flex items-center justify-center">
                <span className="text-2xl">🖼️</span>
              </div>
            </div>
          </div>

          <div className="bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800 p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-zinc-500 dark:text-zinc-400">服装模板</p>
                <p className="text-3xl font-bold text-zinc-950 dark:text-zinc-50 mt-1">
                  {stats.templates}
                </p>
              </div>
              <div className="h-12 w-12 rounded-lg bg-green-100 dark:bg-green-900/30 flex items-center justify-center">
                <span className="text-2xl">👕</span>
              </div>
            </div>
          </div>
        </div>
      )}

      <div>
        <h3 className="text-lg font-semibold text-zinc-950 dark:text-zinc-50 mb-4">
          快速开始
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {features.map((feature) => (
            <button
              key={feature.tab}
              onClick={() => onTabChange(feature.tab)}
              className={`block p-6 rounded-lg border transition-all hover:shadow-md text-left w-full ${feature.color}`}
            >
              <div className="flex items-start gap-4">
                <div className="text-4xl">{feature.icon}</div>
                <div className="flex-1">
                  <h4 className={`text-lg font-semibold mb-2 ${feature.textColor}`}>
                    {feature.title}
                  </h4>
                  <p className="text-sm text-zinc-600 dark:text-zinc-400">
                    {feature.description}
                  </p>
                </div>
                <svg
                  className={`h-5 w-5 flex-shrink-0 ${feature.textColor}`}
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 5l7 7-7 7"
                  />
                </svg>
              </div>
            </button>
          ))}
        </div>
      </div>

      <div className="mt-8 p-6 bg-zinc-100 dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800">
        <h3 className="text-lg font-semibold text-zinc-950 dark:text-zinc-50 mb-2">
          💡 使用提示
        </h3>
        <ul className="space-y-2 text-sm text-zinc-600 dark:text-zinc-400">
          <li className="flex items-start gap-2">
            <span className="text-zinc-950 dark:text-zinc-50">•</span>
            <span>首先上传您的设计灵感图片，AI 会自动分析风格和图案类型</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-zinc-950 dark:text-zinc-50">•</span>
            <span>在生成图案时，系统会根据分析结果推荐最佳图案类型</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-zinc-950 dark:text-zinc-50">•</span>
            <span>所有设计都会自动保存版本历史，您可以随时回滚到之前的版本</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-zinc-950 dark:text-zinc-50">•</span>
            <span>浏览服装模板库，选择合适的模板应用您的设计</span>
          </li>
        </ul>
      </div>
    </div>
  );
}
