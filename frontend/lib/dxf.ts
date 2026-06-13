type DxfPair = {
  code: number;
  value: string;
};

type DxfPoint = {
  x: number;
  y: number;
};

type DxfLine = {
  type: 'line';
  start: DxfPoint;
  end: DxfPoint;
};

type DxfPolyline = {
  type: 'polyline';
  points: DxfPoint[];
  closed: boolean;
};

type DxfCircle = {
  type: 'circle';
  center: DxfPoint;
  radius: number;
};

type DxfArc = {
  type: 'arc';
  center: DxfPoint;
  radius: number;
  startAngle: number;
  endAngle: number;
};

type DxfEntity = DxfLine | DxfPolyline | DxfCircle | DxfArc;

export type DxfRenderedRegion = {
  label: string;
  points: Array<[number, number]>;
};

export type DxfRenderResult = {
  dataUrl: string;
  width: number;
  height: number;
  regions: DxfRenderedRegion[];
};

type Bounds = {
  minX: number;
  minY: number;
  maxX: number;
  maxY: number;
};

const DEFAULT_CANVAS_WIDTH = 900;
const DEFAULT_CANVAS_HEIGHT = 1100;
const CANVAS_PADDING = 40;

function parseNumber(value: string | undefined): number | null {
  if (value === undefined) {
    return null;
  }
  const parsed = Number(value.trim());
  return Number.isFinite(parsed) ? parsed : null;
}

function pairsFromDxf(text: string): DxfPair[] {
  const lines = text.replace(/^\uFEFF/, '').split(/\r?\n/);
  const pairs: DxfPair[] = [];

  for (let index = 0; index + 1 < lines.length; index += 2) {
    const code = Number(lines[index].trim());
    if (!Number.isFinite(code)) {
      continue;
    }
    pairs.push({ code, value: lines[index + 1].trim() });
  }

  return pairs;
}

function entityEndIndex(pairs: DxfPair[], startIndex: number): number {
  let index = startIndex + 1;
  while (index < pairs.length && pairs[index].code !== 0) {
    index += 1;
  }
  return index;
}

function groupNumber(groups: DxfPair[], code: number): number | null {
  return parseNumber(groups.find((pair) => pair.code === code)?.value);
}

function parseLine(groups: DxfPair[]): DxfLine | null {
  const x1 = groupNumber(groups, 10);
  const y1 = groupNumber(groups, 20);
  const x2 = groupNumber(groups, 11);
  const y2 = groupNumber(groups, 21);

  if (x1 === null || y1 === null || x2 === null || y2 === null) {
    return null;
  }

  return { type: 'line', start: { x: x1, y: y1 }, end: { x: x2, y: y2 } };
}

function parseCircle(groups: DxfPair[]): DxfCircle | null {
  const x = groupNumber(groups, 10);
  const y = groupNumber(groups, 20);
  const radius = groupNumber(groups, 40);

  if (x === null || y === null || radius === null || radius <= 0) {
    return null;
  }

  return { type: 'circle', center: { x, y }, radius };
}

function parseArc(groups: DxfPair[]): DxfArc | null {
  const x = groupNumber(groups, 10);
  const y = groupNumber(groups, 20);
  const radius = groupNumber(groups, 40);
  const startAngle = groupNumber(groups, 50);
  const endAngle = groupNumber(groups, 51);

  if (x === null || y === null || radius === null || radius <= 0 || startAngle === null || endAngle === null) {
    return null;
  }

  return { type: 'arc', center: { x, y }, radius, startAngle, endAngle };
}

function parseLightweightPolyline(groups: DxfPair[]): DxfPolyline | null {
  const points: DxfPoint[] = [];
  const flags = groupNumber(groups, 70) ?? 0;

  for (let index = 0; index < groups.length; index += 1) {
    if (groups[index].code !== 10) {
      continue;
    }

    const x = parseNumber(groups[index].value);
    let y: number | null = null;
    for (let yIndex = index + 1; yIndex < groups.length; yIndex += 1) {
      if (groups[yIndex].code === 10) {
        break;
      }
      if (groups[yIndex].code === 20) {
        y = parseNumber(groups[yIndex].value);
        break;
      }
    }

    if (x !== null && y !== null) {
      points.push({ x, y });
    }
  }

  return points.length >= 2 ? { type: 'polyline', points, closed: (flags & 1) === 1 } : null;
}

function parseLegacyPolyline(pairs: DxfPair[], startIndex: number): { entity: DxfPolyline | null; nextIndex: number } {
  const points: DxfPoint[] = [];
  const headerEnd = entityEndIndex(pairs, startIndex);
  const flags = groupNumber(pairs.slice(startIndex + 1, headerEnd), 70) ?? 0;
  let index = headerEnd;

  while (index < pairs.length) {
    const marker = pairs[index];
    if (marker.code !== 0) {
      index += 1;
      continue;
    }
    if (marker.value === 'SEQEND') {
      return {
        entity: points.length >= 2 ? { type: 'polyline', points, closed: (flags & 1) === 1 } : null,
        nextIndex: entityEndIndex(pairs, index),
      };
    }
    if (marker.value !== 'VERTEX') {
      return {
        entity: points.length >= 2 ? { type: 'polyline', points, closed: (flags & 1) === 1 } : null,
        nextIndex: index,
      };
    }

    const vertexEnd = entityEndIndex(pairs, index);
    const vertexGroups = pairs.slice(index + 1, vertexEnd);
    const x = groupNumber(vertexGroups, 10);
    const y = groupNumber(vertexGroups, 20);
    if (x !== null && y !== null) {
      points.push({ x, y });
    }
    index = vertexEnd;
  }

  return {
    entity: points.length >= 2 ? { type: 'polyline', points, closed: (flags & 1) === 1 } : null,
    nextIndex: index,
  };
}

export function parseDxfEntities(text: string): DxfEntity[] {
  const pairs = pairsFromDxf(text);
  const entities: DxfEntity[] = [];
  let index = 0;

  while (index < pairs.length) {
    const pair = pairs[index];
    if (pair.code !== 0) {
      index += 1;
      continue;
    }

    if (pair.value === 'POLYLINE') {
      const parsed = parseLegacyPolyline(pairs, index);
      if (parsed.entity) {
        entities.push(parsed.entity);
      }
      index = parsed.nextIndex;
      continue;
    }

    const endIndex = entityEndIndex(pairs, index);
    const groups = pairs.slice(index + 1, endIndex);
    const entity = pair.value === 'LINE'
      ? parseLine(groups)
      : pair.value === 'LWPOLYLINE'
      ? parseLightweightPolyline(groups)
      : pair.value === 'CIRCLE'
      ? parseCircle(groups)
      : pair.value === 'ARC'
      ? parseArc(groups)
      : null;

    if (entity) {
      entities.push(entity);
    }
    index = endIndex;
  }

  return entities;
}

function emptyBounds(): Bounds {
  return { minX: Infinity, minY: Infinity, maxX: -Infinity, maxY: -Infinity };
}

function includePoint(bounds: Bounds, point: DxfPoint) {
  bounds.minX = Math.min(bounds.minX, point.x);
  bounds.minY = Math.min(bounds.minY, point.y);
  bounds.maxX = Math.max(bounds.maxX, point.x);
  bounds.maxY = Math.max(bounds.maxY, point.y);
}

function includeCircle(bounds: Bounds, center: DxfPoint, radius: number) {
  includePoint(bounds, { x: center.x - radius, y: center.y - radius });
  includePoint(bounds, { x: center.x + radius, y: center.y + radius });
}

function calculateBounds(entities: DxfEntity[]): Bounds {
  const bounds = emptyBounds();

  for (const entity of entities) {
    if (entity.type === 'line') {
      includePoint(bounds, entity.start);
      includePoint(bounds, entity.end);
    } else if (entity.type === 'polyline') {
      for (const point of entity.points) {
        includePoint(bounds, point);
      }
    } else {
      includeCircle(bounds, entity.center, entity.radius);
    }
  }

  return bounds;
}

function degreesToRadians(degrees: number): number {
  return degrees * Math.PI / 180;
}

function circleRegionPoints(center: DxfPoint, radius: number, project: (point: DxfPoint) => DxfPoint): Array<[number, number]> {
  const points: Array<[number, number]> = [];
  const segments = 64;

  for (let index = 0; index < segments; index += 1) {
    const angle = (Math.PI * 2 * index) / segments;
    const projected = project({
      x: center.x + Math.cos(angle) * radius,
      y: center.y + Math.sin(angle) * radius,
    });
    points.push([projected.x, projected.y]);
  }

  return points;
}

export function renderDxfPreview(text: string): DxfRenderResult {
  const entities = parseDxfEntities(text);
  if (entities.length === 0) {
    throw new Error('DXF 中没有可渲染的 2D 图元（支持 LINE、LWPOLYLINE、POLYLINE、CIRCLE、ARC）');
  }

  const bounds = calculateBounds(entities);
  if (!Number.isFinite(bounds.minX) || !Number.isFinite(bounds.minY) || !Number.isFinite(bounds.maxX) || !Number.isFinite(bounds.maxY)) {
    throw new Error('DXF 图元坐标无效');
  }

  const drawingWidth = Math.max(1, bounds.maxX - bounds.minX);
  const drawingHeight = Math.max(1, bounds.maxY - bounds.minY);
  const canvas = document.createElement('canvas');
  canvas.width = DEFAULT_CANVAS_WIDTH;
  canvas.height = DEFAULT_CANVAS_HEIGHT;

  const context = canvas.getContext('2d');
  if (!context) {
    throw new Error('浏览器不支持 Canvas 渲染');
  }

  context.fillStyle = '#ffffff';
  context.fillRect(0, 0, canvas.width, canvas.height);
  context.strokeStyle = '#18181b';
  context.lineCap = 'round';
  context.lineJoin = 'round';

  const scale = Math.min(
    (canvas.width - CANVAS_PADDING * 2) / drawingWidth,
    (canvas.height - CANVAS_PADDING * 2) / drawingHeight
  );
  context.lineWidth = Math.max(1, 1.5 / Math.max(scale, 0.1));

  const project = (point: DxfPoint): DxfPoint => ({
    x: CANVAS_PADDING + (point.x - bounds.minX) * scale,
    y: canvas.height - CANVAS_PADDING - (point.y - bounds.minY) * scale,
  });
  const regions: DxfRenderedRegion[] = [];

  context.save();
  context.beginPath();
  for (const [index, entity] of entities.entries()) {
    if (entity.type === 'line') {
      const start = project(entity.start);
      const end = project(entity.end);
      context.moveTo(start.x, start.y);
      context.lineTo(end.x, end.y);
    } else if (entity.type === 'polyline') {
      const first = project(entity.points[0]);
      context.moveTo(first.x, first.y);
      for (const point of entity.points.slice(1)) {
        const projected = project(point);
        context.lineTo(projected.x, projected.y);
      }
      if (entity.closed) {
        context.closePath();
        regions.push({
          label: `DXF 区域 ${regions.length + 1}`,
          points: entity.points.map((point) => {
            const projected = project(point);
            return [projected.x, projected.y];
          }),
        });
      }
    } else if (entity.type === 'circle') {
      const center = project(entity.center);
      context.moveTo(center.x + entity.radius * scale, center.y);
      context.arc(center.x, center.y, entity.radius * scale, 0, Math.PI * 2);
      regions.push({
        label: `DXF 圆形区域 ${index + 1}`,
        points: circleRegionPoints(entity.center, entity.radius, project),
      });
    } else {
      const center = project(entity.center);
      context.moveTo(center.x, center.y);
      context.arc(
        center.x,
        center.y,
        entity.radius * scale,
        -degreesToRadians(entity.endAngle),
        -degreesToRadians(entity.startAngle)
      );
    }
  }
  context.stroke();
  context.restore();

  return {
    dataUrl: canvas.toDataURL('image/png'),
    width: canvas.width,
    height: canvas.height,
    regions,
  };
}

export function renderDxfToDataUrl(text: string): string {
  return renderDxfPreview(text).dataUrl;
}
