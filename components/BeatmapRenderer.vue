<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue"

type NoteKind = "circle" | "slider" | "slider-body" | "slider-repeat" | "slider-end" | "spinner" | "hold"

interface PropNote {
  sourceIndex: number
  x: number
  y: number
  timeMs: number
  objectType: number
  kind: NoteKind
}

interface Point {
  x: number
  y: number
}

interface VisualObject {
  kind: "circle" | "slider" | "spinner"
  sourceIndex: number
  x: number
  y: number
  timeMs: number
  endTimeMs: number
  slides: number
  comboColor: [number, number, number]
  polyline?: Point[]
  bodyCanvas?: OffscreenCanvas
  bodyOffsetX?: number
  bodyOffsetY?: number
}

const props = defineProps<{
  notes: PropNote[]
  currentTimeMs: number
  approachRate: number
  circleSize: number
  osuText: string
}>()

const OSU_WIDTH = 512
const OSU_HEIGHT = 384
const PAD = 80
const CANVAS_WIDTH = OSU_WIDTH + PAD * 2
const CANVAS_HEIGHT = OSU_HEIGHT + PAD * 2

const COMBO_COLORS: Array<[number, number, number]> = [
  [255, 199, 0],
  [102, 204, 0],
  [72, 208, 255],
  [242, 24, 57],
  [255, 128, 0],
  [196, 102, 255],
]

const rendererWrapRef = ref<HTMLDivElement | null>(null)
const canvasRef = ref<HTMLCanvasElement | null>(null)
const canvasDisplayWidth = ref(CANVAS_WIDTH)
const canvasDisplayHeight = ref(CANVAS_HEIGHT)
let ctx: CanvasRenderingContext2D | null = null
let rafId: number | null = null
let resizeObserver: ResizeObserver | null = null
let visualObjects: VisualObject[] = []

const canvasStyle = computed(() => ({
  width: `${canvasDisplayWidth.value}px`,
  height: `${canvasDisplayHeight.value}px`,
}))

function updateCanvasDisplaySize() {
  const wrap = rendererWrapRef.value

  if (!wrap) {
    return
  }

  const width = wrap.clientWidth
  const height = wrap.clientHeight

  if (width <= 0 || height <= 0) {
    return
  }

  const canvasAspect = CANVAS_WIDTH / CANVAS_HEIGHT
  const wrapAspect = width / height

  if (wrapAspect > canvasAspect) {
    canvasDisplayHeight.value = height
    canvasDisplayWidth.value = height * canvasAspect
    return
  }

  canvasDisplayWidth.value = width
  canvasDisplayHeight.value = width / canvasAspect
}

// ─── Osu difficulty helpers ──────────────────────────────────────────────────

function getPreemptMs(ar: number): number {
  return ar <= 5 ? 1800 - 120 * ar : 1200 - 150 * (ar - 5)
}

function getCircleRadius(cs: number): number {
  return 54.4 - 4.48 * cs
}

// ─── Slider path flattening ──────────────────────────────────────────────────

function parseSliderCurves(text: string): Map<number, { type: string; points: Point[]; pixelLength: number }> {
  const result = new Map<number, { type: string; points: Point[]; pixelLength: number }>()
  const lines = text.split(/\r?\n/)
  let inHitObjects = false
  let hitObjectIndex = 0

  for (const rawLine of lines) {
    const line = rawLine.trim()

    if (line === "[HitObjects]") {
      inHitObjects = true
      continue
    }

    if (line.startsWith("[") && line.endsWith("]")) {
      inHitObjects = false
      continue
    }

    if (!inHitObjects || !line || line.startsWith("//")) {
      continue
    }

    const parts = line.split(",")
    const x = Number(parts[0])
    const y = Number(parts[1])
    const timeMs = Number(parts[2])

    if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(timeMs)) {
      continue
    }

    const objectType = Number(parts[3])
    const isSlider = (objectType & 2) !== 0

    if (isSlider && parts[5]) {
      const [curveTypePart = "B", ...rawPoints] = parts[5].split("|")
      const points: Point[] = [{ x, y }]

      for (const rawPoint of rawPoints) {
        const colonIdx = rawPoint.indexOf(":")

        if (colonIdx !== -1) {
          points.push({ x: Number(rawPoint.slice(0, colonIdx)), y: Number(rawPoint.slice(colonIdx + 1)) })
        }
      }

      result.set(hitObjectIndex, {
        type: curveTypePart,
        points,
        pixelLength: Number(parts[7]) || 0,
      })
    }

    hitObjectIndex++
  }

  return result
}

function evaluateBezier(pts: Point[], t: number): Point {
  let current = pts
  while (current.length > 1) {
    const next: Point[] = []
    for (let i = 0; i < current.length - 1; i++) {
      next.push({
        x: current[i].x * (1 - t) + current[i + 1].x * t,
        y: current[i].y * (1 - t) + current[i + 1].y * t,
      })
    }
    current = next
  }
  return current[0]!
}

function subdivideRecursive(pts: Point[], t0: number, t1: number, tolerance: number, result: Point[]) {
  const mid = (t0 + t1) / 2
  const p0 = evaluateBezier(pts, t0)
  const p1 = evaluateBezier(pts, t1)
  const pm = evaluateBezier(pts, mid)
  const dx = p1.x - p0.x
  const dy = p1.y - p0.y
  const len = Math.sqrt(dx * dx + dy * dy)

  if (len < tolerance * 2) {
    result.push(p1)
    return
  }

  const dist = len > 0
    ? Math.abs(dx * (p0.y - pm.y) - dy * (p0.x - pm.x)) / len
    : Math.sqrt((pm.x - p0.x) ** 2 + (pm.y - p0.y) ** 2)

  if (dist <= tolerance) {
    result.push(p1)
    return
  }

  subdivideRecursive(pts, t0, mid, tolerance, result)
  subdivideRecursive(pts, mid, t1, tolerance, result)
}

function flattenBezierSegments(points: Point[]): Point[] {
  // Split multi-segment bezier sliders at duplicate anchor points
  const segments: Point[][] = []
  let current: Point[] = []

  for (let i = 0; i < points.length; i++) {
    current.push(points[i]!)

    const next = points[i + 1]
    if (next && points[i]!.x === next.x && points[i]!.y === next.y) {
      segments.push(current)
      current = []
    }
  }

  if (current.length > 0) segments.push(current)

  const result: Point[] = []

  for (const seg of segments) {
    if (seg.length === 0) continue
    if (seg.length === 1) {
      if (result.length === 0) result.push(seg[0]!)
      continue
    }

    if (result.length === 0) result.push(seg[0]!)
    subdivideRecursive(seg, 0, 1, 0.5, result)
  }

  return result
}

function flattenPerfectCircle(p0: Point, p1: Point, p2: Point): Point[] {
  const ax = p0.x, ay = p0.y
  const bx = p1.x, by = p1.y
  const cx = p2.x, cy = p2.y
  const D = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))

  if (Math.abs(D) < 1e-6) {
    return [p0, p2]
  }

  const sq = (n: number) => n * n
  const ux = (sq(ax) + sq(ay)) * (by - cy) + (sq(bx) + sq(by)) * (cy - ay) + (sq(cx) + sq(cy)) * (ay - by)
  const uy = (sq(ax) + sq(ay)) * (cx - bx) + (sq(bx) + sq(by)) * (ax - cx) + (sq(cx) + sq(cy)) * (bx - ax)
  const centerX = ux / D
  const centerY = uy / D
  const radius = Math.sqrt(sq(ax - centerX) + sq(ay - centerY))
  const startAngle = Math.atan2(ay - centerY, ax - centerX)
  const endAngle = Math.atan2(cy - centerY, cx - centerX)
  const cross = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
  const clockwise = cross < 0
  let sweep = endAngle - startAngle

  if (clockwise && sweep > 0) sweep -= 2 * Math.PI
  if (!clockwise && sweep < 0) sweep += 2 * Math.PI

  const arcLen = Math.abs(radius * sweep)
  const steps = Math.max(8, Math.round(arcLen / 2))
  const pts: Point[] = []

  for (let i = 0; i <= steps; i++) {
    const angle = startAngle + sweep * (i / steps)
    pts.push({ x: centerX + radius * Math.cos(angle), y: centerY + radius * Math.sin(angle) })
  }

  return pts
}

function trimPolyline(pts: Point[], targetLength: number): Point[] {
  if (pts.length <= 1 || targetLength <= 0) return pts.slice(0, 1)

  const result: Point[] = [pts[0]!]
  let accumulated = 0

  for (let i = 1; i < pts.length; i++) {
    const dx = pts[i]!.x - pts[i - 1]!.x
    const dy = pts[i]!.y - pts[i - 1]!.y
    const segLen = Math.sqrt(dx * dx + dy * dy)

    if (accumulated + segLen >= targetLength) {
      const t = segLen > 0 ? (targetLength - accumulated) / segLen : 0
      result.push({ x: pts[i - 1]!.x + dx * t, y: pts[i - 1]!.y + dy * t })
      return result
    }

    result.push(pts[i]!)
    accumulated += segLen
  }

  return result
}

function flattenPath(type: string, points: Point[], pixelLength: number): Point[] {
  if (points.length === 0) return []

  let polyline: Point[]

  if (type === "L") {
    polyline = points
  } else if (type === "P" && points.length === 3) {
    polyline = flattenPerfectCircle(points[0]!, points[1]!, points[2]!)
  } else {
    polyline = flattenBezierSegments(points)
  }

  return trimPolyline(polyline, pixelLength)
}

function polylineLength(pts: Point[]): number {
  let len = 0
  for (let i = 1; i < pts.length; i++) {
    const dx = pts[i]!.x - pts[i - 1]!.x
    const dy = pts[i]!.y - pts[i - 1]!.y
    len += Math.sqrt(dx * dx + dy * dy)
  }
  return len
}

function getPolylinePointAt(pts: Point[], t: number): Point {
  if (pts.length === 0) return { x: 0, y: 0 }
  if (pts.length === 1 || t <= 0) return pts[0]!
  if (t >= 1) return pts[pts.length - 1]!

  const totalLen = polylineLength(pts)
  const target = totalLen * t
  let accumulated = 0

  for (let i = 1; i < pts.length; i++) {
    const dx = pts[i]!.x - pts[i - 1]!.x
    const dy = pts[i]!.y - pts[i - 1]!.y
    const segLen = Math.sqrt(dx * dx + dy * dy)

    if (accumulated + segLen >= target) {
      const segT = segLen > 0 ? (target - accumulated) / segLen : 0
      return { x: pts[i - 1]!.x + dx * segT, y: pts[i - 1]!.y + dy * segT }
    }

    accumulated += segLen
  }

  return pts[pts.length - 1]!
}

// ─── Visual object building ──────────────────────────────────────────────────

function buildVisualObjects(): VisualObject[] {
  const sliderCurves = parseSliderCurves(props.osuText)
  const sliderEndTimes = new Map<number, number>()
  const sliderRepeats = new Map<number, number>()

  for (const note of props.notes) {
    if (note.kind === "slider-end") {
      sliderEndTimes.set(note.sourceIndex, note.timeMs)
    } else if (note.kind === "slider-repeat") {
      sliderRepeats.set(note.sourceIndex, (sliderRepeats.get(note.sourceIndex) ?? 0) + 1)
    }
  }

  const result: VisualObject[] = []
  let colorIndex = 0
  let isFirst = true

  for (const note of props.notes) {
    if (note.kind !== "circle" && note.kind !== "slider" && note.kind !== "spinner" && note.kind !== "hold") {
      continue
    }

    const newCombo = (note.objectType & 4) !== 0
    if (newCombo && !isFirst) {
      const colorSkip = (note.objectType >> 4) & 7
      colorIndex = (colorIndex + 1 + colorSkip) % COMBO_COLORS.length
    }
    isFirst = false

    const comboColor = COMBO_COLORS[colorIndex]!

    if (note.kind === "slider") {
      const curveData = sliderCurves.get(note.sourceIndex)
      const endTimeMs = sliderEndTimes.get(note.sourceIndex) ?? note.timeMs
      const repeats = sliderRepeats.get(note.sourceIndex) ?? 0
      const slides = 1 + repeats

      const polyline = curveData
        ? flattenPath(curveData.type, curveData.points, curveData.pixelLength)
        : [{ x: note.x, y: note.y }]

      result.push({
        kind: "slider",
        sourceIndex: note.sourceIndex,
        x: note.x,
        y: note.y,
        timeMs: note.timeMs,
        endTimeMs,
        slides,
        comboColor,
        polyline: polyline.length > 0 ? polyline : [{ x: note.x, y: note.y }],
      })
    } else {
      result.push({
        kind: note.kind === "spinner" ? "spinner" : "circle",
        sourceIndex: note.sourceIndex,
        x: note.x,
        y: note.y,
        timeMs: note.timeMs,
        endTimeMs: note.timeMs,
        slides: 1,
        comboColor,
      })
    }
  }

  return result
}

function bakeSliderBodies(radius: number) {
  for (const obj of visualObjects) {
    if (obj.kind !== "slider" || !obj.polyline || obj.polyline.length < 2) continue

    const pts = obj.polyline
    const [r, g, b] = obj.comboColor
    // outer stroke half-width is radius+3, add 1px extra for anti-aliasing
    const margin = Math.ceil(radius + 4)
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity

    for (const p of pts) {
      if (p.x - margin < minX) minX = p.x - margin
      if (p.y - margin < minY) minY = p.y - margin
      if (p.x + margin > maxX) maxX = p.x + margin
      if (p.y + margin > maxY) maxY = p.y + margin
    }

    const w = Math.max(1, Math.ceil(maxX - minX))
    const h = Math.max(1, Math.ceil(maxY - minY))
    const offscreen = new OffscreenCanvas(w, h)
    const octx = offscreen.getContext("2d")!

    const drawStroke = (width: number, style: string) => {
      octx.beginPath()
      octx.moveTo(pts[0]!.x - minX, pts[0]!.y - minY)
      for (let i = 1; i < pts.length; i++) {
        octx.lineTo(pts[i]!.x - minX, pts[i]!.y - minY)
      }
      octx.strokeStyle = style
      octx.lineWidth = width
      octx.lineCap = "round"
      octx.lineJoin = "round"
      octx.stroke()
    }

    drawStroke(radius * 2 + 6, "rgba(255,255,255,0.85)")
    drawStroke(radius * 2 - 2, `rgba(${Math.round(r * 0.45)},${Math.round(g * 0.45)},${Math.round(b * 0.45)},0.92)`)

    obj.bodyCanvas = offscreen
    obj.bodyOffsetX = minX
    obj.bodyOffsetY = minY
  }
}

// ─── Drawing ─────────────────────────────────────────────────────────────────

function drawHitCircle(c: CanvasRenderingContext2D, x: number, y: number, radius: number, r: number, g: number, b: number) {
  c.beginPath()
  c.arc(x, y, radius, 0, Math.PI * 2)
  c.fillStyle = `rgba(${r},${g},${b},0.82)`
  c.fill()
  c.strokeStyle = "rgba(255,255,255,0.9)"
  c.lineWidth = 3
  c.stroke()

  // Inner ring
  c.beginPath()
  c.arc(x, y, Math.max(2, radius - 7), 0, Math.PI * 2)
  c.strokeStyle = "rgba(255,255,255,0.35)"
  c.lineWidth = 1.5
  c.stroke()
}

function render(timeMs: number) {
  if (!ctx) return

  const preemptMs = getPreemptMs(props.approachRate)
  const fadeInMs = preemptMs * 0.4
  const radius = getCircleRadius(props.circleSize)

  ctx.clearRect(0, 0, CANVAS_WIDTH, CANVAS_HEIGHT)
  ctx.fillStyle = "#0f172a"
  ctx.fillRect(0, 0, CANVAS_WIDTH, CANVAS_HEIGHT)

  ctx.save()
  ctx.translate(PAD, PAD)

  // Playfield border
  ctx.strokeStyle = "rgba(255,255,255,0.07)"
  ctx.lineWidth = 1
  ctx.strokeRect(0.5, 0.5, OSU_WIDTH - 1, OSU_HEIGHT - 1)

  // Collect visible objects (behind-first order = larger timeMs first)
  const visible: Array<{ obj: VisualObject; timeUntilHit: number }> = []

  for (const obj of visualObjects) {
    const timeUntilHit = obj.timeMs - timeMs

    if (timeUntilHit > preemptMs) continue

    if (obj.kind === "slider") {
      if (timeMs > obj.endTimeMs + 200) continue
    } else {
      if (timeUntilHit < -200) continue
    }

    visible.push({ obj, timeUntilHit })
  }

  visible.sort((a, b) => b.obj.timeMs - a.obj.timeMs)

  for (const { obj, timeUntilHit } of visible) {
    const approachProgress = Math.max(0, 1 - Math.max(0, timeUntilHit) / preemptMs)
    const fadeAlpha = Math.min(1, (preemptMs - Math.max(0, timeUntilHit)) / fadeInMs)
    // Sliders stay fully opaque until endTimeMs, then fade over 200ms
    const timeAfterEnd = timeMs - obj.endTimeMs
    const hitAlpha = obj.kind === "slider"
      ? (timeAfterEnd > 0 ? Math.max(0, 1 - timeAfterEnd / 200) : 1)
      : (timeUntilHit < 0 ? Math.max(0, 1 + timeUntilHit / 200) : 1)
    const alpha = Math.min(fadeAlpha, hitAlpha)

    const [r, g, b] = obj.comboColor

    ctx.globalAlpha = alpha

    if (obj.kind === "spinner") {
      const spinnerRadius = 80
      const cx = OSU_WIDTH / 2
      const cy = OSU_HEIGHT / 2
      const spinProgress = timeUntilHit < 0
        ? Math.max(0, 1 + timeUntilHit / (obj.endTimeMs - obj.timeMs || 1000))
        : approachProgress

      ctx.beginPath()
      ctx.arc(cx, cy, spinnerRadius, -Math.PI / 2, -Math.PI / 2 + spinProgress * Math.PI * 2)
      ctx.strokeStyle = "rgba(255,255,255,0.55)"
      ctx.lineWidth = 4
      ctx.stroke()

      ctx.beginPath()
      ctx.arc(cx, cy, 6, 0, Math.PI * 2)
      ctx.strokeStyle = "rgba(255,255,255,0.75)"
      ctx.lineWidth = 2
      ctx.stroke()
    } else if (obj.kind === "slider") {
      // Draw pre-baked body
      if (obj.bodyCanvas && obj.bodyOffsetX !== undefined && obj.bodyOffsetY !== undefined) {
        ctx.drawImage(obj.bodyCanvas, obj.bodyOffsetX, obj.bodyOffsetY)
      }

      // Slider head
      drawHitCircle(ctx, obj.x, obj.y, radius, r, g, b)

      // Slider end cap (hollow circle at tail)
      if (obj.polyline && obj.polyline.length > 0) {
        const endPt = obj.polyline[obj.polyline.length - 1]!
        ctx.beginPath()
        ctx.arc(endPt.x, endPt.y, radius, 0, Math.PI * 2)
        ctx.strokeStyle = `rgba(${r},${g},${b},0.6)`
        ctx.lineWidth = 3
        ctx.stroke()
      }

      // Repeat arrows
      if (obj.slides > 1 && obj.polyline && obj.polyline.length > 1) {
        const drawArrow = (tip: Point, from: Point) => {
          const dx = tip.x - from.x
          const dy = tip.y - from.y
          const len = Math.sqrt(dx * dx + dy * dy)
          if (len < 0.1) return
          const nx = dx / len
          const ny = dy / len
          const arrowSize = radius * 0.65
          ctx!.beginPath()
          ctx!.moveTo(tip.x + nx * arrowSize, tip.y + ny * arrowSize)
          ctx!.lineTo(tip.x - ny * arrowSize * 0.55 - nx * arrowSize * 0.55, tip.y + nx * arrowSize * 0.55 - ny * arrowSize * 0.55)
          ctx!.lineTo(tip.x + ny * arrowSize * 0.55 - nx * arrowSize * 0.55, tip.y - nx * arrowSize * 0.55 - ny * arrowSize * 0.55)
          ctx!.closePath()
          ctx!.fillStyle = "rgba(255,255,255,0.85)"
          ctx!.fill()
        }

        const pts = obj.polyline
        const tailPt = pts[pts.length - 1]!
        const nearTail = pts[Math.max(0, pts.length - 2)]!
        // Arrow at tail always (slider goes back from there)
        drawArrow(tailPt, nearTail)
        // Arrow at head for 3+ slides (it bounces back to start)
        if (obj.slides >= 3) {
          drawArrow(pts[0]!, pts[1]!)
        }
      }

      // Slider ball during active slide
      if (timeUntilHit <= 0 && timeMs <= obj.endTimeMs && obj.polyline && obj.polyline.length > 0) {
        const totalDuration = obj.endTimeMs - obj.timeMs
        const rawProgress = totalDuration > 0 ? (timeMs - obj.timeMs) / totalDuration : 0

        // Handle repeats: each span is 1/slides of total duration
        const spanProgress = rawProgress * obj.slides
        const spanIndex = Math.floor(spanProgress)
        const spanT = spanProgress - spanIndex
        const isForward = spanIndex % 2 === 0
        const ballT = isForward ? spanT : 1 - spanT

        const ballPos = getPolylinePointAt(obj.polyline, ballT)

        // Follow circle
        ctx.beginPath()
        ctx.arc(ballPos.x, ballPos.y, radius, 0, Math.PI * 2)
        ctx.strokeStyle = `rgba(${r},${g},${b},0.55)`
        ctx.lineWidth = 3
        ctx.stroke()

        // Ball
        ctx.beginPath()
        ctx.arc(ballPos.x, ballPos.y, radius * 0.55, 0, Math.PI * 2)
        ctx.fillStyle = `rgb(${r},${g},${b})`
        ctx.fill()
        ctx.strokeStyle = "rgba(255,255,255,0.9)"
        ctx.lineWidth = 2
        ctx.stroke()
      }
    } else {
      drawHitCircle(ctx, obj.x, obj.y, radius, r, g, b)
    }

    // Approach circle (only while approaching)
    if (timeUntilHit > 0) {
      const approachScale = 1 + 4 * (1 - approachProgress)
      const approachX = obj.kind === "spinner" ? OSU_WIDTH / 2 : obj.x
      const approachY = obj.kind === "spinner" ? OSU_HEIGHT / 2 : obj.y

      ctx.beginPath()
      ctx.arc(approachX, approachY, radius * approachScale, 0, Math.PI * 2)
      ctx.strokeStyle = `rgb(${r},${g},${b})`
      ctx.lineWidth = 2
      ctx.stroke()
    }
  }

  ctx.globalAlpha = 1
  ctx.restore()

  // Time label in padding area (unaffected by translate)
  ctx.fillStyle = "rgba(255,255,255,0.25)"
  ctx.font = "10px monospace"
  ctx.fillText(`${(timeMs / 1000).toFixed(2)}s`, 4, 12)
}

function loop() {
  render(props.currentTimeMs)
  rafId = requestAnimationFrame(loop)
}

function rebuild() {
  if (!props.osuText) {
    visualObjects = []
    return
  }

  visualObjects = buildVisualObjects()
  bakeSliderBodies(getCircleRadius(props.circleSize))
}

watch(() => props.osuText, rebuild, { immediate: true })

onMounted(() => {
  ctx = canvasRef.value?.getContext("2d") ?? null
  updateCanvasDisplaySize()
  resizeObserver = new ResizeObserver(updateCanvasDisplaySize)

  if (rendererWrapRef.value) {
    resizeObserver.observe(rendererWrapRef.value)
  }

  rafId = requestAnimationFrame(loop)
})

onBeforeUnmount(() => {
  if (rafId !== null) cancelAnimationFrame(rafId)
  resizeObserver?.disconnect()
})
</script>

<template>
  <div ref="rendererWrapRef" class="renderer-wrap">
    <canvas
      ref="canvasRef"
      :width="CANVAS_WIDTH"
      :height="CANVAS_HEIGHT"
      class="renderer-canvas"
      :style="canvasStyle"
    />
  </div>
</template>

<style scoped>
.renderer-wrap {
  display: flex;
  justify-content: center;
  align-items: center;
  min-width: 0;
  min-height: 0;
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: #0f172a;
}

.renderer-canvas {
  flex: 0 0 auto;
  display: block;
  max-width: 100%;
  max-height: 100%;
}
</style>
