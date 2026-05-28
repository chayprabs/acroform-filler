import clsx from "clsx";
import type { ReactNode } from "react";

export interface ResultPaneProps {
  tabs: Array<{ id: string; label: string; content: ReactNode }>;
  activeTab: string;
  onTabChange: (id: string) => void;
  className?: string;
}

export function ResultPane({
  tabs,
  activeTab,
  onTabChange,
  className,
}: ResultPaneProps) {
  const current = tabs.find((tab) => tab.id === activeTab) ?? tabs[0];

  return (
    <div className={clsx("rounded-xl border border-slate-200 dark:border-slate-700", className)}>
      <div className="flex border-b border-slate-200 dark:border-slate-700">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            className={clsx(
              "px-4 py-2 text-sm font-medium",
              tab.id === activeTab
                ? "border-b-2 border-blue-600 text-blue-600"
                : "text-slate-600 hover:text-slate-900 dark:text-slate-300",
            )}
            onClick={() => onTabChange(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div className="p-4">{current?.content}</div>
    </div>
  );
}
