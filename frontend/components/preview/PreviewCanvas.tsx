'use client';

import { useEffect, useRef, useState } from 'react';
import { Stage, Layer, Image as KonvaImage, Group, Transformer } from 'react-konva';
import Konva from 'konva';
import { Position } from '@/types/preview';

interface PreviewCanvasProps {
  templateUrl: string | null;
  patternUrl: string | null;
  position: Position;
  onPositionChange: (position: Position) => void;
  width?: number;
  height?: number;
}

export default function PreviewCanvas({
  templateUrl,
  patternUrl,
  position,
  onPositionChange,
  width = 800,
  height = 600,
}: PreviewCanvasProps) {
  const [templateImage, setTemplateImage] = useState<HTMLImageElement | null>(null);
  const [patternImage, setPatternImage] = useState<HTMLImageElement | null>(null);
  const patternRef = useRef<Konva.Image>(null);
  const transformerRef = useRef<Konva.Transformer>(null);

  useEffect(() => {
    if (templateUrl) {
      const img = new window.Image();
      img.crossOrigin = 'anonymous';
      img.src = templateUrl;
      img.onload = () => setTemplateImage(img);
    }
  }, [templateUrl]);

  useEffect(() => {
    if (patternUrl) {
      const img = new window.Image();
      img.crossOrigin = 'anonymous';
      img.src = patternUrl;
      img.onload = () => setPatternImage(img);
    }
  }, [patternUrl]);

  useEffect(() => {
    if (patternRef.current && transformerRef.current) {
      transformerRef.current.nodes([patternRef.current]);
      transformerRef.current.getLayer()?.batchDraw();
    }
  }, [patternImage]);

  const handleDragEnd = (e: Konva.KonvaEventObject<DragEvent>) => {
    const node = e.target;
    onPositionChange({
      ...position,
      x: node.x(),
      y: node.y(),
    });
  };

  const handleTransformEnd = () => {
    if (!patternRef.current) return;

    const node = patternRef.current;
    const scaleX = node.scaleX();

    node.scaleX(1);
    node.scaleY(1);

    onPositionChange({
      x: node.x(),
      y: node.y(),
      scale: position.scale * scaleX,
      rotation: node.rotation(),
      opacity: position.opacity,
    });
  };

  return (
    <div className="border border-gray-300 rounded-lg overflow-hidden bg-gray-50">
      <Stage width={width} height={height}>
        <Layer>
          {templateImage && (
            <KonvaImage
              image={templateImage}
              width={width}
              height={height}
              listening={false}
            />
          )}
          {patternImage && (
            <Group>
              <KonvaImage
                ref={patternRef}
                image={patternImage}
                x={position.x}
                y={position.y}
                scaleX={position.scale}
                scaleY={position.scale}
                rotation={position.rotation}
                opacity={position.opacity || 1}
                draggable
                onDragEnd={handleDragEnd}
                onTransformEnd={handleTransformEnd}
              />
              <Transformer
                ref={transformerRef}
                rotateEnabled
                enabledAnchors={[
                  'top-left',
                  'top-right',
                  'bottom-left',
                  'bottom-right',
                ]}
                boundBoxFunc={(oldBox, newBox) => {
                  if (newBox.width < 20 || newBox.height < 20) {
                    return oldBox;
                  }
                  return newBox;
                }}
              />
            </Group>
          )}
        </Layer>
      </Stage>
    </div>
  );
}
