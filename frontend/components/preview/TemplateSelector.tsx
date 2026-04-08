'use client';

import { Template } from '@/types/preview';

interface TemplateSelectorProps {
  templates: Template[];
  selectedTemplateId: number | null;
  onSelectTemplate: (templateId: number) => void;
}

export default function TemplateSelector({
  templates,
  selectedTemplateId,
  onSelectTemplate,
}: TemplateSelectorProps) {
  return (
    <div className="w-full">
      <h3 className="text-lg font-semibold mb-4">Select Template</h3>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {templates.map((template) => (
          <button
            key={template.id}
            onClick={() => onSelectTemplate(template.id)}
            className={`
              relative aspect-square rounded-lg border-2 overflow-hidden
              transition-all duration-200 hover:scale-105
              ${
                selectedTemplateId === template.id
                  ? 'border-blue-500 ring-2 ring-blue-200'
                  : 'border-gray-300 hover:border-gray-400'
              }
            `}
          >
            <img
              src={template.image_path}
              alt={template.name}
              className="w-full h-full object-cover"
            />
            <div className="absolute bottom-0 left-0 right-0 bg-black bg-opacity-60 text-white text-sm py-2 px-3">
              {template.name}
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
