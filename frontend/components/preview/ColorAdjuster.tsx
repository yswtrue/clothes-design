'use client';

import { ColorAdjustment } from '@/types/preview';

interface ColorAdjusterProps {
  colors: ColorAdjustment;
  onColorsChange: (colors: ColorAdjustment) => void;
}

export default function ColorAdjuster({ colors, onColorsChange }: ColorAdjusterProps) {
  const handleHueChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onColorsChange({ ...colors, hue: parseFloat(e.target.value) });
  };

  const handleSaturationChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onColorsChange({ ...colors, saturation: parseFloat(e.target.value) });
  };

  const handleBrightnessChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onColorsChange({ ...colors, brightness: parseFloat(e.target.value) });
  };

  const handleReset = () => {
    onColorsChange({ hue: 0, saturation: 0, brightness: 0 });
  };

  return (
    <div className="w-full p-6 bg-white rounded-lg border border-gray-200">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-semibold">Color Adjustment</h3>
        <button
          onClick={handleReset}
          className="px-3 py-1 text-sm text-gray-600 hover:text-gray-900 border border-gray-300 rounded hover:bg-gray-50"
        >
          Reset
        </button>
      </div>

      <div className="space-y-6">
        <div>
          <label className="flex justify-between items-center mb-2">
            <span className="text-sm font-medium text-gray-700">Hue</span>
            <span className="text-sm text-gray-500">{colors.hue.toFixed(0)}°</span>
          </label>
          <input
            type="range"
            min="-180"
            max="180"
            step="1"
            value={colors.hue}
            onChange={handleHueChange}
            className="w-full h-2 bg-gradient-to-r from-red-500 via-green-500 to-blue-500 rounded-lg appearance-none cursor-pointer"
          />
        </div>

        <div>
          <label className="flex justify-between items-center mb-2">
            <span className="text-sm font-medium text-gray-700">Saturation</span>
            <span className="text-sm text-gray-500">{colors.saturation.toFixed(0)}%</span>
          </label>
          <input
            type="range"
            min="-100"
            max="100"
            step="1"
            value={colors.saturation}
            onChange={handleSaturationChange}
            className="w-full h-2 bg-gradient-to-r from-gray-400 to-pink-500 rounded-lg appearance-none cursor-pointer"
          />
        </div>

        <div>
          <label className="flex justify-between items-center mb-2">
            <span className="text-sm font-medium text-gray-700">Brightness</span>
            <span className="text-sm text-gray-500">{colors.brightness.toFixed(0)}%</span>
          </label>
          <input
            type="range"
            min="-100"
            max="100"
            step="1"
            value={colors.brightness}
            onChange={handleBrightnessChange}
            className="w-full h-2 bg-gradient-to-r from-black via-gray-500 to-white rounded-lg appearance-none cursor-pointer"
          />
        </div>
      </div>
    </div>
  );
}
