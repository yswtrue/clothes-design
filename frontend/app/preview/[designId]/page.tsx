'use client';

import { useState, useEffect, useCallback, use } from 'react';
import { fetchDesign, fetchTemplates, updateDesign } from '@/lib/preview';
import { Design, Template, Position, ColorAdjustment, PreviewPageState } from '@/types/preview';
import TemplateSelector from '@/components/preview/TemplateSelector';
import PreviewCanvas from '@/components/preview/PreviewCanvas';
import ColorAdjuster from '@/components/preview/ColorAdjuster';

interface PageProps {
  params: Promise<{ designId: string }>;
}

export default function PreviewPage({ params }: PageProps) {
  const { designId } = use(params);
  const [state, setState] = useState<PreviewPageState>('loading');
  const [design, setDesign] = useState<Design | null>(null);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState<number | null>(null);
  const [position, setPosition] = useState<Position>({
    x: 0,
    y: 0,
    scale: 1.0,
    rotation: 0,
    opacity: 1,
  });
  const [colors, setColors] = useState<ColorAdjustment>({
    hue: 0,
    saturation: 0,
    brightness: 0,
  });
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setState('loading');
    setError(null);

    try {
      const [designData, templatesData] = await Promise.all([
        fetchDesign(parseInt(designId)),
        fetchTemplates(),
      ]);

      setDesign(designData);
      setTemplates(templatesData);

      if (designData.preview_state) {
        setSelectedTemplateId(designData.preview_state.template_id);
        setPosition(designData.preview_state.position);
        setColors(designData.preview_state.colors);
      }

      setState('ready');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load data');
      setState('error');
    }
  }, [designId]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadData();
  }, [loadData]);

  const handleTemplateSelect = async (templateId: number) => {
    setSelectedTemplateId(templateId);
    await handleSave({ template_id: templateId });
  };

  const handlePositionChange = async (newPosition: Position) => {
    setPosition(newPosition);
    await handleSave({ position: newPosition });
  };

  const handleColorsChange = async (newColors: ColorAdjustment) => {
    setColors(newColors);
    await handleSave({ colors: newColors });
  };

  const handleSave = async (updates: {
    template_id?: number;
    position?: Position;
    colors?: ColorAdjustment;
  }) => {
    if (!design) return;

    setState('updating');
    try {
      const updatedDesign = await updateDesign(design.id, updates);
      setDesign(updatedDesign);
      setState('ready');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save changes');
      setState('error');
    }
  };

  const selectedTemplate = templates.find((t) => t.id === selectedTemplateId);
  const patternUrl = design?.preview_state?.pattern_url || null;

  if (state === 'loading') {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading design...</p>
        </div>
      </div>
    );
  }

  if (state === 'error' || !design) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="text-red-500 text-xl mb-4">⚠️</div>
          <p className="text-gray-800 mb-4">{error || 'Failed to load design'}</p>
          <button
            onClick={loadData}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-7xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Preview Editor</h1>
          <p className="text-gray-600">
            Design: <span className="font-semibold">{design.name}</span>
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div className="lg:col-span-2 space-y-8">
            <PreviewCanvas
              templateUrl={selectedTemplate?.image_path || null}
              patternUrl={patternUrl}
              position={position}
              onPositionChange={handlePositionChange}
              width={800}
              height={600}
            />

            <TemplateSelector
              templates={templates}
              selectedTemplateId={selectedTemplateId}
              onSelectTemplate={handleTemplateSelect}
            />
          </div>

          <div className="space-y-6">
            <ColorAdjuster colors={colors} onColorsChange={handleColorsChange} />

            <div className="p-6 bg-white rounded-lg border border-gray-200">
              <h3 className="text-lg font-semibold mb-4">Position Controls</h3>
              <div className="space-y-4">
                <div>
                  <label className="flex justify-between items-center mb-2">
                    <span className="text-sm font-medium text-gray-700">Scale</span>
                    <span className="text-sm text-gray-500">{position.scale.toFixed(2)}x</span>
                  </label>
                  <input
                    type="range"
                    min="0.1"
                    max="3"
                    step="0.1"
                    value={position.scale}
                    onChange={(e) =>
                      handlePositionChange({ ...position, scale: parseFloat(e.target.value) })
                    }
                    className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
                  />
                </div>

                <div>
                  <label className="flex justify-between items-center mb-2">
                    <span className="text-sm font-medium text-gray-700">Rotation</span>
                    <span className="text-sm text-gray-500">{position.rotation.toFixed(0)}°</span>
                  </label>
                  <input
                    type="range"
                    min="-180"
                    max="180"
                    step="1"
                    value={position.rotation}
                    onChange={(e) =>
                      handlePositionChange({ ...position, rotation: parseFloat(e.target.value) })
                    }
                    className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
                  />
                </div>

                <div>
                  <label className="flex justify-between items-center mb-2">
                    <span className="text-sm font-medium text-gray-700">Opacity</span>
                    <span className="text-sm text-gray-500">
                      {((position.opacity || 1) * 100).toFixed(0)}%
                    </span>
                  </label>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.01"
                    value={position.opacity || 1}
                    onChange={(e) =>
                      handlePositionChange({ ...position, opacity: parseFloat(e.target.value) })
                    }
                    className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
                  />
                </div>
              </div>
            </div>

            {state === 'updating' && (
              <div className="p-4 bg-blue-50 text-blue-700 rounded-lg text-sm">
                Saving changes...
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
