<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from "vue"

type ToneNamespace = typeof import("tone")

type MapInfo = {
  title: string
  artist: string
  version: string
  creator: string
  audioFilename: string
  beatDivisor: number
  sliderMultiplier: number
}

type HitObjectKind = "circle" | "slider" | "spinner" | "hold"
type HitSlotKind = HitObjectKind | "slider-body" | "slider-end"
type SampleSource = "default" | "custom" | "none"
type SampleBank = "normal" | "soft" | "drum"
type SampleSound = "hitnormal" | "hitwhistle" | "hitfinish" | "hitclap" | "sliderwhistle"

type CustomSample = {
  bank: SampleBank
  sound: SampleSound
  sampleIndex: number
  originalName: string
  fileName: string
  mimeType: string
  data: ArrayBuffer
}

type OsuNote = {
  id: string
  index: number
  sourceIndex: number
  x: number
  y: number
  timeMs: number
  sourceTimeMs: number
  objectType: number
  kind: HitSlotKind
}

type Track = {
  id: number
  name: string
  sampleName: string
  sampleUrl: string | null
  sampleSource: SampleSource
  customSampleBank: SampleBank
  customSampleSound: SampleSound
  customSampleIndex: number
  customSample: CustomSample | null
  hits: boolean[]
}

type TimingPoint = {
  id: string
  timeMs: number
  beatLengthMs: number
  meter: number
  bpm: number
}

type RawTimingPoint = {
  timeMs: number
  beatLengthMs: number
  meter: number
  sampleSet: number
  uninherited: boolean
}

type RawEdgeSet = {
  normalSet: number
  additionSet: number
}

type RawHitObject = {
  sourceIndex: number
  x: number
  y: number
  timeMs: number
  objectType: number
  kind: HitObjectKind
  hitSound: number
  hitSample: string
  edgeSounds: number[]
  edgeSets: RawEdgeSet[]
  slides: number
  pixelLength: number
}

type SnapLine = {
  id: string
  timeMs: number
  kind: "division" | "beat" | "measure"
}

type DefaultSample = {
  name: string
  url: string
}

type CopiedPattern = {
  sourceTrackName: string
  durationMs: number
  hits: Array<{
    offsetMs: number
  }>
}

type ExportSample = {
  sampleName: string
  bank: SampleBank
  sound: SampleSound
  sampleIndex: number
  trackIndex: number
  fileName: string
  data?: ArrayBuffer
}

type HitsoundLayer = {
  normal?: ExportSample
  addition?: ExportSample
  hitSoundBits: number
}

type SourceHitsoundAssignment = {
  head?: HitsoundLayer
  sliderBody?: HitsoundLayer
  sliderEnd?: HitsoundLayer
}

type SavedCustomSample = Omit<CustomSample, "data"> & {
  dataUrl: string
}

type SavedTrack = {
  name: string
  sampleName: string
  sampleSource: SampleSource
  customSampleBank: SampleBank
  customSampleSound: SampleSound
  customSampleIndex: number
  customSample: SavedCustomSample | null
  hits: boolean[]
}

type SavedProject = {
  version: 1
  osuFileName: string
  osuText: string
  backingAudioName: string
  backingAudioDataUrl: string | null
  fallbackCustomSample: SavedCustomSample | null
  tracks: SavedTrack[]
  activeTrackIndex: number
  currentTimeMs: number
  playbackAnchorMs: number
  audioOffsetMs: number
  snapPlaybackToGrid: boolean
  followPlayhead: boolean
  pixelsPerSecond: number
}

const runtimeConfig = useRuntimeConfig()
const appBaseUrl = `${runtimeConfig.app.baseURL || "/"}`.replace(/\/?$/, "/")

function resolvePublicAssetUrl(path: string) {
  const normalizedPath = path.replace(/^\/+/, "")

  return `${appBaseUrl}${normalizedPath}`
}

const laneLabelWidth = 190
const markerDiameter = 22
const defaultSamples: DefaultSample[] = [
  { name: "drum-hitnormal.wav", url: resolvePublicAssetUrl("samples/default/drum-hitnormal.wav") },
  { name: "drum-hitclap.wav", url: resolvePublicAssetUrl("samples/default/drum-hitclap.wav") },
  { name: "drum-hitfinish.wav", url: resolvePublicAssetUrl("samples/default/drum-hitfinish.wav") },
  { name: "drum-hitwhistle.wav", url: resolvePublicAssetUrl("samples/default/drum-hitwhistle.wav") },
  { name: "drum-sliderwhistle.wav", url: resolvePublicAssetUrl("samples/default/drum-sliderwhistle.wav") },
  { name: "normal-hitnormal.wav", url: resolvePublicAssetUrl("samples/default/normal-hitnormal.wav") },
  { name: "normal-hitclap.wav", url: resolvePublicAssetUrl("samples/default/normal-hitclap.wav") },
  { name: "normal-hitfinish.wav", url: resolvePublicAssetUrl("samples/default/normal-hitfinish.wav") },
  { name: "normal-hitwhistle.wav", url: resolvePublicAssetUrl("samples/default/normal-hitwhistle.wav") },
  { name: "normal-sliderwhistle.wav", url: resolvePublicAssetUrl("samples/default/normal-sliderwhistle.wav") },
  { name: "soft-hitnormal.wav", url: resolvePublicAssetUrl("samples/default/soft-hitnormal.wav") },
  { name: "soft-hitclap.wav", url: resolvePublicAssetUrl("samples/default/soft-hitclap.wav") },
  { name: "soft-hitfinish.wav", url: resolvePublicAssetUrl("samples/default/soft-hitfinish.wav") },
  { name: "soft-hitwhistle.wav", url: resolvePublicAssetUrl("samples/default/soft-hitwhistle.wav") },
  { name: "soft-sliderwhistle.wav", url: resolvePublicAssetUrl("samples/default/soft-sliderwhistle.wav") },
]
const sampleTypeOptions: Array<{
  label: string
  bank: SampleBank
  sound: SampleSound
}> = [
  { label: "normal-hitnormal", bank: "normal", sound: "hitnormal" },
  { label: "normal-hitclap", bank: "normal", sound: "hitclap" },
  { label: "normal-hitfinish", bank: "normal", sound: "hitfinish" },
  { label: "normal-hitwhistle", bank: "normal", sound: "hitwhistle" },
  { label: "normal-sliderwhistle", bank: "normal", sound: "sliderwhistle" },
  { label: "soft-hitnormal", bank: "soft", sound: "hitnormal" },
  { label: "soft-hitclap", bank: "soft", sound: "hitclap" },
  { label: "soft-hitfinish", bank: "soft", sound: "hitfinish" },
  { label: "soft-hitwhistle", bank: "soft", sound: "hitwhistle" },
  { label: "soft-sliderwhistle", bank: "soft", sound: "sliderwhistle" },
  { label: "drum-hitnormal", bank: "drum", sound: "hitnormal" },
  { label: "drum-hitclap", bank: "drum", sound: "hitclap" },
  { label: "drum-hitfinish", bank: "drum", sound: "hitfinish" },
  { label: "drum-hitwhistle", bank: "drum", sound: "hitwhistle" },
  { label: "drum-sliderwhistle", bank: "drum", sound: "sliderwhistle" },
]
const trackPalette = [
  {
    accent: "#22d3ee",
    accentDark: "#0891b2",
    accentMuted: "rgba(34, 211, 238, 0.36)",
    accentSoft: "rgba(34, 211, 238, 0.12)",
  },
  {
    accent: "#a78bfa",
    accentDark: "#7c3aed",
    accentMuted: "rgba(167, 139, 250, 0.36)",
    accentSoft: "rgba(167, 139, 250, 0.12)",
  },
  {
    accent: "#fb7185",
    accentDark: "#e11d48",
    accentMuted: "rgba(251, 113, 133, 0.36)",
    accentSoft: "rgba(251, 113, 133, 0.12)",
  },
  {
    accent: "#fbbf24",
    accentDark: "#d97706",
    accentMuted: "rgba(251, 191, 36, 0.36)",
    accentSoft: "rgba(251, 191, 36, 0.12)",
  },
  {
    accent: "#34d399",
    accentDark: "#059669",
    accentMuted: "rgba(52, 211, 153, 0.36)",
    accentSoft: "rgba(52, 211, 153, 0.12)",
  },
  {
    accent: "#60a5fa",
    accentDark: "#2563eb",
    accentMuted: "rgba(96, 165, 250, 0.36)",
    accentSoft: "rgba(96, 165, 250, 0.12)",
  },
]
const pixelsPerSecond = ref(180)
const notes = ref<OsuNote[]>([])
const mapInfo = ref<MapInfo | null>(null)
const timingPoints = ref<TimingPoint[]>([])
const tracks = ref<Track[]>([])
const originalOsuText = ref("")
const originalOsuFileName = ref("")
const hitObjectLineIndices = ref<number[]>([])
const currentTimeMs = ref(0)
const playbackAnchorMs = ref(0)
const isPlaying = ref(false)
const audioOffsetMs = ref(0)
const snapPlaybackToGrid = ref(true)
const followPlayhead = ref(true)
const backingAudioUrl = ref<string | null>(null)
const backingAudioName = ref("")
const backingAudioDataUrl = ref<string | null>(null)
const backingDurationMs = ref(0)
const backingAudio = ref<HTMLAudioElement | null>(null)
const timelineScroll = ref<HTMLDivElement | null>(null)
const timelineScrollLeft = ref(0)
const timelineViewportWidth = ref(1_200)
const activeTrackIndex = ref(0)
const selectionTrackIndex = ref<number | null>(null)
const selectionAnchorMs = ref<number | null>(null)
const selectionFocusMs = ref<number | null>(null)
const isSelectingRange = ref(false)
const copiedPattern = ref<CopiedPattern | null>(null)
const clipboardStatus = ref("")
const suppressNextTimelineClick = ref(false)
const isTrackDrawerOpen = ref(true)
const isPanningTimeline = ref(false)
const fallbackCustomSample = ref<CustomSample | null>(null)

let trackIdSeed = 0
let tone: ToneNamespace | null = null
let animationFrameId: number | null = null
let backingStartTimeoutId: number | null = null
let players = new Map<number, import("tone").Player>()
let timelinePanPointerId: number | null = null
let timelinePanStartX = 0
let timelinePanStartY = 0
let timelinePanStartScrollLeft = 0
let timelinePanStartScrollTop = 0

tracks.value = [
  createTrack("Kick", 0),
  createTrack("Snare", 0),
  createTrack("Hat", 0),
]

const durationMs = computed(() => {
  const lastNoteMs = notes.value.at(-1)?.timeMs ?? 0

  return Math.max(lastNoteMs + 1_000, backingDurationMs.value)
})

const playbackStartMs = computed(() => notes.value[0]?.timeMs ?? 0)
const timelineStartMs = computed(() => playbackStartMs.value)
const visibleDurationMs = computed(() =>
  Math.max(1_000, durationMs.value - timelineStartMs.value),
)

const timelineWidth = computed(() => {
  const noteAreaWidth = Math.max(
    760,
    (visibleDurationMs.value / 1_000) * pixelsPerSecond.value,
  )

  return `${laneLabelWidth + noteAreaWidth + 120}px`
})

const mapTitle = computed(() => {
  if (!mapInfo.value) {
    return "No map loaded"
  }

  const title = [mapInfo.value.artist, mapInfo.value.title].filter(Boolean).join(" - ")
  const version = mapInfo.value.version ? ` [${mapInfo.value.version}]` : ""

  return `${title || "Untitled map"}${version}`
})

const selectedHitsCount = computed(() =>
  tracks.value.reduce(
    (total, track) => total + track.hits.filter(Boolean).length,
    0,
  ),
)

const snapDivisor = computed(() => Math.max(1, mapInfo.value?.beatDivisor ?? 4))

const timingSummary = computed(() => {
  if (!timingPoints.value.length) {
    return "No BPM timing point found"
  }

  const bpms = timingPoints.value.map((point) => point.bpm)
  const minBpm = Math.min(...bpms)
  const maxBpm = Math.max(...bpms)
  const bpmLabel =
    Math.abs(minBpm - maxBpm) < 0.01
      ? `${formatNumber(minBpm)} BPM`
      : `${formatNumber(minBpm)}-${formatNumber(maxBpm)} BPM`

  return `${bpmLabel}, 1/${snapDivisor.value} snap, ${timingPoints.value.length} timing section${
    timingPoints.value.length === 1 ? "" : "s"
  }`
})

const snapLines = computed<SnapLine[]>(() => {
  if (!timingPoints.value.length || durationMs.value <= 0) {
    return []
  }

  const lines: SnapLine[] = []
  const maxLines = 5_000

  for (const [index, timingPoint] of timingPoints.value.entries()) {
    const nextTimingPoint = timingPoints.value[index + 1]
    const sectionEndMs = Math.min(nextTimingPoint?.timeMs ?? durationMs.value, durationMs.value)
    const sectionStartMs = Math.max(timingPoint.timeMs, timelineStartMs.value)
    const stepMs = timingPoint.beatLengthMs / snapDivisor.value

    if (stepMs <= 0 || sectionEndMs <= sectionStartMs) {
      continue
    }

    const firstStep = Math.max(0, Math.ceil((sectionStartMs - timingPoint.timeMs) / stepMs))
    const lastStep = Math.floor((sectionEndMs - timingPoint.timeMs) / stepMs)

    for (let step = firstStep; step <= lastStep; step += 1) {
      if (lines.length >= maxLines) {
        return lines
      }

      const timeMs = timingPoint.timeMs + step * stepMs
      const beatIndex = Math.round(step / snapDivisor.value)
      const isBeat = step % snapDivisor.value === 0
      const isMeasure = isBeat && beatIndex % timingPoint.meter === 0

      lines.push({
        id: `${timingPoint.id}-${step}`,
        timeMs,
        kind: isMeasure ? "measure" : isBeat ? "beat" : "division",
      })
    }
  }

  return lines
})

const rulerNotes = computed(() => {
  if (notes.value.length <= 48) {
    return notes.value
  }

  const interval = Math.ceil(notes.value.length / 48)

  return notes.value.filter((_, index) => index % interval === 0)
})

const markerSlots = computed(() => notes.value.filter((note) => note.kind !== "slider-body"))
const sliderBodySlots = computed(() => notes.value.filter((note) => note.kind === "slider-body"))
const virtualBufferMs = computed(() => Math.max(2_000, (timelineViewportWidth.value / pixelsPerSecond.value) * 1_000))
const visibleRangeStartMs = computed(() => {
  const visibleStartPx = Math.max(0, timelineScrollLeft.value - laneLabelWidth)

  return Math.max(
    timelineStartMs.value,
    timelineStartMs.value + (visibleStartPx / pixelsPerSecond.value) * 1_000 - virtualBufferMs.value,
  )
})
const visibleRangeEndMs = computed(() => {
  const visibleEndPx = Math.max(0, timelineScrollLeft.value + timelineViewportWidth.value - laneLabelWidth)

  return Math.min(
    durationMs.value,
    timelineStartMs.value + (visibleEndPx / pixelsPerSecond.value) * 1_000 + virtualBufferMs.value,
  )
})
const visibleSnapLines = computed(() =>
  snapLines.value.filter(
    (line) => line.timeMs >= visibleRangeStartMs.value && line.timeMs <= visibleRangeEndMs.value,
  ),
)
const visibleMarkerSlots = computed(() =>
  markerSlots.value.filter((note) => {
    const displayMs = displayTimeMs(note)

    return displayMs >= visibleRangeStartMs.value && displayMs <= visibleRangeEndMs.value
  }),
)
const sliderEndSlotsBySource = computed(() => {
  const endSlots = new Map<number, OsuNote>()

  for (const note of notes.value) {
    if (note.kind === "slider-end") {
      endSlots.set(note.sourceIndex, note)
    }
  }

  return endSlots
})
const visibleSliderBodySlots = computed(() =>
  sliderBodySlots.value.filter((note) => {
    const startMs = snapPlaybackToGrid.value
      ? getSnappedTimeMs(note.sourceTimeMs)
      : note.sourceTimeMs
    const endSlot = sliderEndSlotsBySource.value.get(note.sourceIndex)
    const endMs = endSlot ? displayTimeMs(endSlot) : displayTimeMs(note)

    return endMs >= visibleRangeStartMs.value && startMs <= visibleRangeEndMs.value
  }),
)
const hasSelection = computed(
  () =>
    selectionTrackIndex.value !== null &&
    selectionAnchorMs.value !== null &&
    selectionFocusMs.value !== null &&
    selectionEndMs.value > selectionStartMs.value,
)
const selectionStartMs = computed(() => {
  if (selectionAnchorMs.value === null || selectionFocusMs.value === null) {
    return 0
  }

  return Math.min(selectionAnchorMs.value, selectionFocusMs.value)
})
const selectionEndMs = computed(() => {
  if (selectionAnchorMs.value === null || selectionFocusMs.value === null) {
    return 0
  }

  return Math.max(selectionAnchorMs.value, selectionFocusMs.value)
})
const selectionDurationMs = computed(() => Math.max(0, selectionEndMs.value - selectionStartMs.value))

const canPlay = computed(() => notes.value.length > 0)

function createTrack(name: string, noteCount: number): Track {
  trackIdSeed += 1
  const defaultSample = defaultSamples[(trackIdSeed - 1) % defaultSamples.length] ?? null

  return {
    id: trackIdSeed,
    name,
    sampleName: defaultSample?.name ?? "No sample",
    sampleUrl: defaultSample?.url ?? null,
    sampleSource: defaultSample ? "default" : "none",
    customSampleBank: "normal",
    customSampleSound: "hitnormal",
    customSampleIndex: 1,
    customSample: null,
    hits: Array(noteCount).fill(false),
  }
}

function createTrackForSample(sampleName: string, hits: boolean[]): Track {
  trackIdSeed += 1

  const defaultSample = defaultSamples.find((sample) => sample.name === sampleName)
  const parsedSample = parseSampleName(sampleName)

  return {
    id: trackIdSeed,
    name: sampleName.replace(/\.wav$/i, ""),
    sampleName,
    sampleUrl: defaultSample?.url ?? null,
    sampleSource: defaultSample ? "default" : "none",
    customSampleBank: parsedSample?.bank ?? "normal",
    customSampleSound: parsedSample?.sound ?? "hitnormal",
    customSampleIndex: parsedSample?.sampleIndex ?? 1,
    customSample: null,
    hits,
  }
}

async function handleOsuUpload(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]

  if (!file) {
    return
  }

  stopPlayback()

  const text = await file.text()
  const parsed = parseOsuFile(text)

  originalOsuText.value = text
  originalOsuFileName.value = file.name
  hitObjectLineIndices.value = parsed.hitObjectLineIndices
  mapInfo.value = parsed.info
  notes.value = parsed.notes
  timingPoints.value = parsed.timingPoints
  tracks.value =
    parsed.importedTrackHits.size > 0
      ? [...parsed.importedTrackHits.entries()].map(([sampleName, hits]) =>
          createTrackForSample(sampleName, hits),
        )
      : tracks.value.map((track) => ({
          ...track,
          hits: Array(parsed.notes.length).fill(false),
        }))
  currentTimeMs.value = playbackStartMs.value
  playbackAnchorMs.value = playbackStartMs.value
  input.value = ""
  timelineScroll.value?.scrollTo({ left: 0 })
  await nextTick()
  updateTimelineViewport()
}

function parseOsuFile(text: string) {
  const rawLines = text.split(/\r?\n/)
  const metadata = new Map<string, string>()
  const editorSettings = new Map<string, string>()
  const difficultySettings = new Map<string, string>()
  const hitObjects: RawHitObject[] = []
  const parsedHitObjectLineIndices: number[] = []
  const parsedNotes: OsuNote[] = []
  const parsedTimingPoints: TimingPoint[] = []
  const rawTimingPoints: RawTimingPoint[] = []
  let section = ""
  let audioFilename = ""
  let defaultSampleSetId = 1

  for (const [lineIndex, rawLine] of rawLines.entries()) {
    const line = rawLine.trim()

    if (!line || line.startsWith("//")) {
      continue
    }

    if (line.startsWith("[") && line.endsWith("]")) {
      section = line.slice(1, -1)
      continue
    }

    if (
      section === "General" ||
      section === "Metadata" ||
      section === "Editor" ||
      section === "Difficulty"
    ) {
      const separatorIndex = line.indexOf(":")

      if (separatorIndex === -1) {
        continue
      }

      const key = line.slice(0, separatorIndex).trim()
      const value = line.slice(separatorIndex + 1).trim()

      metadata.set(key, value)

      if (section === "Editor") {
        editorSettings.set(key, value)
      }

      if (section === "Difficulty") {
        difficultySettings.set(key, value)
      }

      if (key === "AudioFilename") {
        audioFilename = value
      }

      if (section === "General" && key === "SampleSet") {
        defaultSampleSetId = getSampleSetIdFromName(value)
      }
    }

    if (section === "TimingPoints") {
      const parts = line.split(",")
      const timeMs = Number(parts[0])
      const beatLengthMs = Number(parts[1])
      const meter = Number(parts[2]) || 4
      const sampleSet = Number(parts[3]) || 0
      const uninherited = parts[6] === undefined || parts[6] === "1"

      if (Number.isFinite(timeMs) && Number.isFinite(beatLengthMs)) {
        rawTimingPoints.push({
          timeMs,
          beatLengthMs,
          meter,
          sampleSet,
          uninherited,
        })
      }

      if (
        uninherited &&
        Number.isFinite(timeMs) &&
        Number.isFinite(beatLengthMs) &&
        beatLengthMs > 0
      ) {
        parsedTimingPoints.push({
          id: `${parsedTimingPoints.length}-${timeMs}`,
          timeMs,
          beatLengthMs,
          meter,
          bpm: 60_000 / beatLengthMs,
        })
      }

      continue
    }

    if (section !== "HitObjects") {
      continue
    }

    const parts = line.split(",")
    const [rawX, rawY, rawTime, rawType] = parts
    const x = Number(rawX)
    const y = Number(rawY)
    const timeMs = Number(rawTime)
    const objectType = Number(rawType)
    const kind = getObjectKind(objectType)
    const hitSound = Number(parts[4]) || 0

    if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(timeMs)) {
      continue
    }

    const sourceIndex = hitObjects.length

    parsedHitObjectLineIndices[sourceIndex] = lineIndex
    hitObjects.push({
      sourceIndex,
      x,
      y,
      timeMs,
      objectType,
      kind,
      hitSound,
      hitSample: getRawHitSample(parts, kind),
      edgeSounds: kind === "slider" ? parseEdgeSounds(parts[8]) : [],
      edgeSets: kind === "slider" ? parseEdgeSets(parts[9]) : [],
      slides: kind === "slider" ? Number(parts[6]) || 1 : 1,
      pixelLength: kind === "slider" ? Number(parts[7]) || 0 : 0,
    })
  }

  rawTimingPoints.sort((a, b) => a.timeMs - b.timeMs)
  hitObjects.sort((a, b) => a.timeMs - b.timeMs)
  parsedNotes.push(
    ...createHitsoundSlots(
      hitObjects,
      rawTimingPoints,
      Number(difficultySettings.get("SliderMultiplier")) || 1.4,
    ),
  )
  parsedNotes.sort((a, b) => a.timeMs - b.timeMs)
  parsedNotes.forEach((note, index) => {
    note.index = index
    note.id = `${index}-${note.timeMs}`
  })

  parsedTimingPoints.sort((a, b) => a.timeMs - b.timeMs)
  parsedTimingPoints.forEach((timingPoint, index) => {
    timingPoint.id = `${index}-${timingPoint.timeMs}`
  })

  return {
    info: {
      title: metadata.get("TitleUnicode") || metadata.get("Title") || "",
      artist: metadata.get("ArtistUnicode") || metadata.get("Artist") || "",
      version: metadata.get("Version") || "",
      creator: metadata.get("Creator") || "",
      audioFilename,
      beatDivisor: Number(editorSettings.get("BeatDivisor")) || 4,
      sliderMultiplier: Number(difficultySettings.get("SliderMultiplier")) || 1.4,
    },
    notes: parsedNotes,
    timingPoints: parsedTimingPoints,
    hitObjectLineIndices: parsedHitObjectLineIndices,
    importedTrackHits: buildImportedTrackHits(
      parsedNotes,
      hitObjects,
      rawTimingPoints,
      defaultSampleSetId,
    ),
  }
}

function createHitsoundSlots(
  hitObjects: RawHitObject[],
  rawTimingPoints: RawTimingPoint[],
  sliderMultiplier: number,
) {
  const slots: OsuNote[] = []

  for (const hitObject of hitObjects) {
    slots.push(createSlot(hitObject, hitObject.kind, hitObject.timeMs))

    if (hitObject.kind !== "slider") {
      continue
    }

    const sliderDurationMs = getSliderDurationMs(
      hitObject,
      rawTimingPoints,
      sliderMultiplier,
    )

    if (sliderDurationMs <= 1) {
      continue
    }

    slots.push(createSlot(hitObject, "slider-body", hitObject.timeMs + sliderDurationMs / 2))
    slots.push(createSlot(hitObject, "slider-end", hitObject.timeMs + sliderDurationMs))
  }

  return slots
}

function createSlot(
  hitObject: RawHitObject,
  kind: HitSlotKind,
  timeMs: number,
): OsuNote {
  return {
    id: `${hitObject.sourceIndex}-${kind}-${timeMs}`,
    index: 0,
    sourceIndex: hitObject.sourceIndex,
    x: hitObject.x,
    y: hitObject.y,
    timeMs,
    sourceTimeMs: hitObject.timeMs,
    objectType: hitObject.objectType,
    kind,
  }
}

function getSampleSetIdFromName(name: string) {
  const normalizedName = name.trim().toLowerCase()

  if (normalizedName === "soft") {
    return 2
  }

  if (normalizedName === "drum") {
    return 3
  }

  return 1
}

function getSampleBankFromId(sampleSetId: number): SampleBank {
  if (sampleSetId === 2) {
    return "soft"
  }

  if (sampleSetId === 3) {
    return "drum"
  }

  return "normal"
}

function parseSampleName(sampleName: string) {
  const match = sampleName
    .toLowerCase()
    .match(/^(normal|soft|drum)-(hitnormal|hitwhistle|hitfinish|hitclap|sliderwhistle)(\d*)\.wav$/)

  if (!match) {
    return null
  }

  return {
    bank: match[1] as SampleBank,
    sound: match[2] as SampleSound,
    sampleIndex: Number(match[3]) || 1,
  }
}

function getRawHitSample(parts: string[], kind: HitObjectKind) {
  if (kind === "slider") {
    return parts[10] || "0:0:0:0:"
  }

  if (kind === "spinner") {
    return parts[6] || "0:0:0:0:"
  }

  if (kind === "hold" && parts[5]) {
    return parts[5].split(":").slice(1).join(":") || "0:0:0:0:"
  }

  return parts[5] || "0:0:0:0:"
}

function parseEdgeSounds(rawEdgeSounds = "") {
  return rawEdgeSounds
    .split("|")
    .filter(Boolean)
    .map((value) => Number(value) || 0)
}

function parseEdgeSets(rawEdgeSets = "") {
  return rawEdgeSets
    .split("|")
    .filter(Boolean)
    .map((edgeSet) => {
      const [normalSet, additionSet] = edgeSet.split(":")

      return {
        normalSet: Number(normalSet) || 0,
        additionSet: Number(additionSet) || 0,
      }
    })
}

function getEffectiveTimingSampleSet(
  rawTimingPoints: RawTimingPoint[],
  timeMs: number,
  defaultSampleSetId: number,
) {
  let activeSampleSet = defaultSampleSetId

  for (const timingPoint of rawTimingPoints) {
    if (timingPoint.timeMs > timeMs) {
      break
    }

    if (timingPoint.sampleSet > 0) {
      activeSampleSet = timingPoint.sampleSet
    }
  }

  return activeSampleSet
}

function addImportedSampleHit(
  importedTrackHits: Map<string, boolean[]>,
  note: OsuNote,
  bank: SampleBank,
  sound: SampleSound,
  sampleIndex: number,
  noteCount: number,
) {
  const sampleName = getSampleFileName(bank, sound, sampleIndex)
  const hits = importedTrackHits.get(sampleName) ?? Array(noteCount).fill(false)

  hits[note.index] = true
  importedTrackHits.set(sampleName, hits)
}

function addImportedLayerHits(
  importedTrackHits: Map<string, boolean[]>,
  note: OsuNote,
  hitSound: number,
  normalSet: number,
  additionSet: number,
  sampleIndex: number,
  effectiveSampleSet: number,
  noteCount: number,
) {
  addImportedSampleHit(
    importedTrackHits,
    note,
    normalSet > 0 ? getSampleBankFromId(normalSet) : "soft",
    "hitnormal",
    normalSet > 0 ? sampleIndex : 1,
    noteCount,
  )

  const effectiveAdditionSet = additionSet || normalSet || effectiveSampleSet
  const additionBank = getSampleBankFromId(effectiveAdditionSet)

  if ((hitSound & getHitSoundBit("hitwhistle")) !== 0) {
    addImportedSampleHit(importedTrackHits, note, additionBank, "hitwhistle", sampleIndex, noteCount)
  }

  if ((hitSound & getHitSoundBit("hitfinish")) !== 0) {
    addImportedSampleHit(importedTrackHits, note, additionBank, "hitfinish", sampleIndex, noteCount)
  }

  if ((hitSound & getHitSoundBit("hitclap")) !== 0) {
    addImportedSampleHit(importedTrackHits, note, additionBank, "hitclap", sampleIndex, noteCount)
  }
}

function buildImportedTrackHits(
  parsedNotes: OsuNote[],
  hitObjects: RawHitObject[],
  rawTimingPoints: RawTimingPoint[],
  defaultSampleSetId: number,
) {
  const importedTrackHits = new Map<string, boolean[]>()
  const hitObjectsBySource = new Map(hitObjects.map((hitObject) => [hitObject.sourceIndex, hitObject]))
  const noteCount = parsedNotes.length

  for (const note of parsedNotes) {
    const hitObject = hitObjectsBySource.get(note.sourceIndex)

    if (!hitObject) {
      continue
    }

    const hitSample = parseHitSample(hitObject.hitSample)
    const sampleIndex = hitSample.index || 1
    const effectiveSampleSet = getEffectiveTimingSampleSet(
      rawTimingPoints,
      hitObject.timeMs,
      defaultSampleSetId,
    )

    if (note.kind === "slider-end") {
      const edgeSound = hitObject.edgeSounds.at(-1) ?? 0
      const edgeSet = hitObject.edgeSets.at(-1) ?? { normalSet: 0, additionSet: 0 }

      addImportedLayerHits(
        importedTrackHits,
        note,
        edgeSound,
        edgeSet.normalSet,
        edgeSet.additionSet,
        sampleIndex,
        effectiveSampleSet,
        noteCount,
      )
      continue
    }

    if (note.kind === "slider-body") {
      // Slider body whistle is encoded through the same slider-level hitSound
      // field that also affects the slider head. Importing it automatically
      // turns ordinary head whistles into body whistles, so keep body slots
      // opt-in in this editor.
      continue
    }

    if (hitObject.kind === "slider") {
      const edgeSound = hitObject.edgeSounds[0] ?? hitObject.hitSound
      const edgeSet = hitObject.edgeSets[0] ?? {
        normalSet: hitSample.normalSet,
        additionSet: hitSample.additionSet,
      }

      addImportedLayerHits(
        importedTrackHits,
        note,
        edgeSound,
        edgeSet.normalSet,
        edgeSet.additionSet,
        sampleIndex,
        effectiveSampleSet,
        noteCount,
      )
      continue
    }

    addImportedLayerHits(
      importedTrackHits,
      note,
      hitObject.hitSound,
      hitSample.normalSet,
      hitSample.additionSet,
      sampleIndex,
      effectiveSampleSet,
      noteCount,
    )
  }

  return importedTrackHits
}

function getSliderDurationMs(
  hitObject: RawHitObject,
  rawTimingPoints: RawTimingPoint[],
  sliderMultiplier: number,
) {
  if (hitObject.pixelLength <= 0 || sliderMultiplier <= 0) {
    return 0
  }

  const timingPoint = getActiveUninheritedTimingPoint(rawTimingPoints, hitObject.timeMs)
  const beatLengthMs = timingPoint?.beatLengthMs ?? 500
  const inheritedPoint = getActiveInheritedTimingPoint(rawTimingPoints, hitObject.timeMs)
  const sliderVelocity =
    inheritedPoint && inheritedPoint.beatLengthMs < 0
      ? -100 / inheritedPoint.beatLengthMs
      : 1

  if (beatLengthMs <= 0 || sliderVelocity <= 0) {
    return 0
  }

  return (
    (hitObject.pixelLength / (sliderMultiplier * 100 * sliderVelocity)) *
    beatLengthMs *
    hitObject.slides
  )
}

function getActiveUninheritedTimingPoint(
  rawTimingPoints: RawTimingPoint[],
  timeMs: number,
) {
  const uninheritedTimingPoints = rawTimingPoints.filter((point) => point.uninherited)
  let activePoint = uninheritedTimingPoints[0] ?? null

  for (const timingPoint of uninheritedTimingPoints) {
    if (timingPoint.timeMs > timeMs) {
      break
    }

    activePoint = timingPoint
  }

  return activePoint
}

function getActiveInheritedTimingPoint(
  rawTimingPoints: RawTimingPoint[],
  timeMs: number,
) {
  let activePoint: RawTimingPoint | null = null

  for (const timingPoint of rawTimingPoints) {
    if (timingPoint.timeMs > timeMs) {
      break
    }

    if (!timingPoint.uninherited) {
      activePoint = timingPoint
    }
  }

  return activePoint
}

function getObjectKind(objectType: number): HitObjectKind {
  if ((objectType & 128) !== 0) {
    return "hold"
  }

  if ((objectType & 8) !== 0) {
    return "spinner"
  }

  if ((objectType & 2) !== 0) {
    return "slider"
  }

  return "circle"
}

function revokeCustomSample(track: Track) {
  if (track.sampleSource === "custom" && track.sampleUrl) {
    URL.revokeObjectURL(track.sampleUrl)
  }
}

function fileToDataUrl(file: File) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader()

    reader.addEventListener("load", () => resolve(String(reader.result ?? "")))
    reader.addEventListener("error", () => reject(reader.error))
    reader.readAsDataURL(file)
  })
}

function arrayBufferToDataUrl(data: ArrayBuffer, mimeType: string) {
  const bytes = new Uint8Array(data)
  let binary = ""

  for (const byte of bytes) {
    binary += String.fromCharCode(byte)
  }

  return `data:${mimeType};base64,${window.btoa(binary)}`
}

function dataUrlToBlob(dataUrl: string) {
  const [header = "", base64 = ""] = dataUrl.split(",")
  const mimeType = header.match(/^data:([^;]+);base64$/)?.[1] || "application/octet-stream"
  const binary = window.atob(base64)
  const bytes = new Uint8Array(binary.length)

  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index)
  }

  return new Blob([bytes], { type: mimeType })
}

async function dataUrlToArrayBuffer(dataUrl: string) {
  return dataUrlToBlob(dataUrl).arrayBuffer()
}

function serializeCustomSample(sample: CustomSample | null): SavedCustomSample | null {
  if (!sample) {
    return null
  }

  return {
    bank: sample.bank,
    sound: sample.sound,
    sampleIndex: sample.sampleIndex,
    originalName: sample.originalName,
    fileName: sample.fileName,
    mimeType: sample.mimeType,
    dataUrl: arrayBufferToDataUrl(sample.data, sample.mimeType),
  }
}

async function deserializeCustomSample(sample: SavedCustomSample | null): Promise<CustomSample | null> {
  if (!sample) {
    return null
  }

  return {
    bank: sample.bank,
    sound: sample.sound,
    sampleIndex: sample.sampleIndex,
    originalName: sample.originalName,
    fileName: sample.fileName,
    mimeType: sample.mimeType,
    data: await dataUrlToArrayBuffer(sample.dataUrl),
  }
}

function revokeSessionObjectUrls() {
  for (const track of tracks.value) {
    revokeCustomSample(track)
  }

  if (backingAudioUrl.value) {
    URL.revokeObjectURL(backingAudioUrl.value)
  }
}

function saveProject() {
  if (!originalOsuText.value) {
    return
  }

  const project: SavedProject = {
    version: 1,
    osuFileName: originalOsuFileName.value,
    osuText: originalOsuText.value,
    backingAudioName: backingAudioName.value,
    backingAudioDataUrl: backingAudioDataUrl.value,
    fallbackCustomSample: serializeCustomSample(fallbackCustomSample.value),
    tracks: tracks.value.map((track) => ({
      name: track.name,
      sampleName: track.sampleName,
      sampleSource: track.sampleSource,
      customSampleBank: track.customSampleBank,
      customSampleSound: track.customSampleSound,
      customSampleIndex: track.customSampleIndex,
      customSample: serializeCustomSample(track.customSample),
      hits: [...track.hits],
    })),
    activeTrackIndex: activeTrackIndex.value,
    currentTimeMs: currentTimeMs.value,
    playbackAnchorMs: playbackAnchorMs.value,
    audioOffsetMs: audioOffsetMs.value,
    snapPlaybackToGrid: snapPlaybackToGrid.value,
    followPlayhead: followPlayhead.value,
    pixelsPerSecond: pixelsPerSecond.value,
  }
  const baseName = originalOsuFileName.value.replace(/\.osu$/i, "") || "hser-project"
  const blob = new Blob([JSON.stringify(project)], { type: "application/json;charset=utf-8" })
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")

  link.href = url
  link.download = `${baseName}.hser.json`
  link.click()
  URL.revokeObjectURL(url)
}

async function handleProjectLoad(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]

  if (!file) {
    return
  }

  stopPlayback()

  const project = JSON.parse(await file.text()) as SavedProject
  const parsed = parseOsuFile(project.osuText)

  revokeSessionObjectUrls()
  originalOsuText.value = project.osuText
  originalOsuFileName.value = project.osuFileName || "loaded.osu"
  hitObjectLineIndices.value = parsed.hitObjectLineIndices
  mapInfo.value = parsed.info
  notes.value = parsed.notes
  timingPoints.value = parsed.timingPoints
  fallbackCustomSample.value = await deserializeCustomSample(project.fallbackCustomSample)

  const restoredTracks: Track[] = []

  for (const savedTrack of project.tracks) {
    trackIdSeed += 1

    const customSample = await deserializeCustomSample(savedTrack.customSample)
    const defaultSample = defaultSamples.find((sample) => sample.name === savedTrack.sampleName)
    const sampleUrl =
      savedTrack.sampleSource === "custom" && customSample
        ? URL.createObjectURL(new Blob([customSample.data], { type: customSample.mimeType }))
        : defaultSample?.url ?? null

    restoredTracks.push({
      id: trackIdSeed,
      name: savedTrack.name,
      sampleName: savedTrack.sampleName,
      sampleUrl,
      sampleSource: savedTrack.sampleSource,
      customSampleBank: savedTrack.customSampleBank,
      customSampleSound: savedTrack.customSampleSound,
      customSampleIndex: savedTrack.customSampleIndex,
      customSample,
      hits: Array.from({ length: parsed.notes.length }, (_, index) => Boolean(savedTrack.hits[index])),
    })
  }

  tracks.value = restoredTracks.length ? restoredTracks : [createTrack("Track 1", parsed.notes.length)]
  backingAudioName.value = project.backingAudioName
  backingAudioDataUrl.value = project.backingAudioDataUrl
  backingDurationMs.value = 0
  backingAudioUrl.value = project.backingAudioDataUrl
    ? URL.createObjectURL(dataUrlToBlob(project.backingAudioDataUrl))
    : null
  currentTimeMs.value = Math.min(Math.max(playbackStartMs.value, project.currentTimeMs), durationMs.value)
  playbackAnchorMs.value = Math.min(Math.max(playbackStartMs.value, project.playbackAnchorMs), durationMs.value)
  activeTrackIndex.value = Math.min(project.activeTrackIndex, Math.max(0, tracks.value.length - 1))
  audioOffsetMs.value = project.audioOffsetMs
  snapPlaybackToGrid.value = project.snapPlaybackToGrid
  followPlayhead.value = project.followPlayhead
  pixelsPerSecond.value = clampZoom(project.pixelsPerSecond)
  copiedPattern.value = null
  clearSelection()
  input.value = ""

  await nextTick()
  timelineScroll.value?.scrollTo({ left: 0, top: 0 })
  updateTimelineViewport()
  centerPlayheadInTimeline()
}

function selectDefaultSample(trackIndex: number, sampleUrl: string) {
  const track = tracks.value[trackIndex]
  const sample = defaultSamples.find((defaultSample) => defaultSample.url === sampleUrl)

  if (!track || !sample) {
    return
  }

  revokeCustomSample(track)
  players.get(track.id)?.dispose()
  players.delete(track.id)
  track.sampleUrl = sample.url
  track.sampleName = sample.name
  track.sampleSource = "default"
  track.customSample = null
}

function handleDefaultSampleChange(event: Event, trackIndex: number) {
  const select = event.target as HTMLSelectElement

  selectDefaultSample(trackIndex, select.value)
}

function handleCustomSampleTypeChange(event: Event, trackIndex: number) {
  const track = tracks.value[trackIndex]
  const select = event.target as HTMLSelectElement
  const option = sampleTypeOptions.find((sampleType) => sampleType.label === select.value)

  if (!track || !option) {
    return
  }

  track.customSampleBank = option.bank
  track.customSampleSound = option.sound
  refreshCustomSampleNaming(track)
}

function getSampleFileName(bank: SampleBank, sound: SampleSound, sampleIndex: number) {
  const normalizedIndex = Math.max(1, Math.round(sampleIndex) || 1)
  const suffix = normalizedIndex <= 1 ? "" : String(normalizedIndex)

  return `${bank}-${sound}${suffix}.wav`
}

function getFallbackExportSample(): ExportSample {
  const customSample = fallbackCustomSample.value

  if (customSample) {
    return {
      sampleName: customSample.fileName,
      bank: customSample.bank,
      sound: customSample.sound,
      sampleIndex: customSample.sampleIndex,
      trackIndex: -1,
      fileName: customSample.fileName,
      data: customSample.data,
    }
  }

  return {
    sampleName: "soft-hitnormal.wav",
    bank: "soft",
    sound: "hitnormal",
    sampleIndex: 1,
    trackIndex: -1,
    fileName: "soft-hitnormal.wav",
  }
}

async function handleFallbackSampleUpload(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]

  if (!file) {
    return
  }

  fallbackCustomSample.value = {
    bank: "soft",
    sound: "hitnormal",
    sampleIndex: 1,
    originalName: file.name,
    fileName: "soft-hitnormal.wav",
    mimeType: file.type || "audio/wav",
    data: await file.arrayBuffer(),
  }
  input.value = ""
}

function refreshCustomSampleNaming(track: Track) {
  if (!track.customSample) {
    return
  }

  const sampleIndex = Math.max(1, Math.round(track.customSampleIndex) || 1)
  const fileName = getSampleFileName(track.customSampleBank, track.customSampleSound, sampleIndex)

  track.customSampleIndex = sampleIndex
  track.customSample.bank = track.customSampleBank
  track.customSample.sound = track.customSampleSound
  track.customSample.sampleIndex = sampleIndex
  track.customSample.fileName = fileName
  track.sampleName = fileName
}

function handleCustomSampleIndexChange(trackIndex: number) {
  const track = tracks.value[trackIndex]

  if (!track) {
    return
  }

  refreshCustomSampleNaming(track)
}

async function handleSampleUpload(event: Event, trackIndex: number) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  const track = tracks.value[trackIndex]

  if (!file || !track) {
    return
  }

  revokeCustomSample(track)

  players.get(track.id)?.dispose()
  players.delete(track.id)

  const data = await file.arrayBuffer()
  const sampleIndex = Math.max(1, Math.round(track.customSampleIndex) || 1)
  const fileName = getSampleFileName(track.customSampleBank, track.customSampleSound, sampleIndex)

  track.sampleUrl = URL.createObjectURL(file)
  track.sampleName = fileName
  track.sampleSource = "custom"
  track.customSampleIndex = sampleIndex
  track.customSample = {
    bank: track.customSampleBank,
    sound: track.customSampleSound,
    sampleIndex,
    originalName: file.name,
    fileName,
    mimeType: file.type || "audio/wav",
    data,
  }
  input.value = ""
}

async function handleBackingUpload(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]

  if (!file) {
    return
  }

  stopPlayback()

  if (backingAudioUrl.value) {
    URL.revokeObjectURL(backingAudioUrl.value)
  }

  backingAudioUrl.value = URL.createObjectURL(file)
  backingAudioName.value = file.name
  backingAudioDataUrl.value = await fileToDataUrl(file)
  backingDurationMs.value = 0
  input.value = ""
}

function handleBackingMetadata() {
  const durationSeconds = backingAudio.value?.duration

  if (durationSeconds && Number.isFinite(durationSeconds)) {
    backingDurationMs.value = durationSeconds * 1_000
  }

  if (backingAudio.value) {
    backingAudio.value.currentTime = playbackAnchorMs.value / 1_000
  }
}

function addTrack() {
  tracks.value.push(createTrack(`Track ${tracks.value.length + 1}`, notes.value.length))
  activeTrackIndex.value = tracks.value.length - 1
}

function removeTrack(trackIndex: number) {
  const [track] = tracks.value.splice(trackIndex, 1)

  if (!track) {
    return
  }

  revokeCustomSample(track)

  players.get(track.id)?.dispose()
  players.delete(track.id)

  activeTrackIndex.value = Math.min(activeTrackIndex.value, Math.max(0, tracks.value.length - 1))

  if (selectionTrackIndex.value === trackIndex) {
    selectionTrackIndex.value = null
    selectionAnchorMs.value = null
    selectionFocusMs.value = null
  } else if (selectionTrackIndex.value !== null && selectionTrackIndex.value > trackIndex) {
    selectionTrackIndex.value -= 1
  }
}

function clearTrack(trackIndex: number) {
  const track = tracks.value[trackIndex]

  if (!track) {
    return
  }

  track.hits = Array(notes.value.length).fill(false)
}

function getExportSampleForTrack(track: Track, trackIndex: number): ExportSample | null {
  if (track.sampleSource === "custom" && track.customSample) {
    return {
      sampleName: track.customSample.fileName,
      bank: track.customSample.bank,
      sound: track.customSample.sound,
      sampleIndex: track.customSample.sampleIndex,
      trackIndex,
      fileName: track.customSample.fileName,
      data: track.customSample.data,
    }
  }

  const parsedSample = parseSampleName(track.sampleName)

  if (!parsedSample) {
    return null
  }

  return {
    sampleName: track.sampleName,
    bank: parsedSample.bank,
    sound: parsedSample.sound,
    sampleIndex: parsedSample.sampleIndex,
    trackIndex,
    fileName: track.sampleName,
  }
}

function mergeSampleIntoLayer(layer: HitsoundLayer, sample: ExportSample) {
  if (sample.sound === "hitnormal") {
    layer.normal = sample
    return
  }

  layer.hitSoundBits |= getHitSoundBit(sample.sound)
  layer.addition = sample
}

function getSelectedHitsoundLayer(noteIndex: number, fallbackNormal: ExportSample) {
  const layer: HitsoundLayer = {
    hitSoundBits: 0,
  }
  let hasSelectedSample = false

  // TODO: Resolve true hitsound conflicts explicitly in the UI. For now, the
  // highest-numbered track wins within each osu field. This means hitnormal
  // picks the highest normal layer, and additions share the highest addition
  // set/index while OR-ing together their clap/finish/whistle bits.
  tracks.value.forEach((track, trackIndex) => {
    if (!track.hits[noteIndex]) {
      return
    }

    const exportSample = getExportSampleForTrack(track, trackIndex)

    if (exportSample) {
      hasSelectedSample = true
      mergeSampleIntoLayer(layer, exportSample)
    }
  })

  if (!layer.normal) {
    layer.normal = fallbackNormal
  }

  return hasSelectedSample ? layer : null
}

function buildSourceHitsoundAssignments() {
  const assignments = new Map<number, SourceHitsoundAssignment>()
  const fallbackSample = getFallbackExportSample()
  const sourceSlots = new Map<number, { hasHead: boolean, hasSliderEnd: boolean }>()

  for (const note of notes.value) {
    const slots = sourceSlots.get(note.sourceIndex) ?? { hasHead: false, hasSliderEnd: false }

    if (note.kind === "slider-end") {
      slots.hasSliderEnd = true
    } else if (note.kind !== "slider-body") {
      slots.hasHead = true
    }

    sourceSlots.set(note.sourceIndex, slots)

    const hitsoundLayer = getSelectedHitsoundLayer(note.index, fallbackSample)

    if (!hitsoundLayer) {
      continue
    }

    const assignment = assignments.get(note.sourceIndex) ?? {}

    if (note.kind === "slider-end") {
      assignment.sliderEnd = hitsoundLayer
    } else if (note.kind === "slider-body") {
      assignment.sliderBody = hitsoundLayer
    } else {
      assignment.head = hitsoundLayer
    }

    assignments.set(note.sourceIndex, assignment)
  }

  for (const [sourceIndex, slots] of sourceSlots.entries()) {
    const assignment = assignments.get(sourceIndex) ?? {}

    if (slots.hasHead && !assignment.head) {
      assignment.head = {
        normal: fallbackSample,
        hitSoundBits: 0,
      }
    }

    if (slots.hasSliderEnd && !assignment.sliderEnd) {
      assignment.sliderEnd = {
        normal: fallbackSample,
        hitSoundBits: 0,
      }
    }

    assignments.set(sourceIndex, assignment)
  }

  return assignments
}

function getHitSoundBit(sound: SampleSound) {
  const bits: Record<SampleSound, number> = {
    hitnormal: 0,
    hitwhistle: 2,
    hitfinish: 4,
    hitclap: 8,
    sliderwhistle: 2,
  }

  return bits[sound]
}

function getSampleSetId(bank: SampleBank) {
  const ids: Record<SampleBank, number> = {
    normal: 1,
    soft: 2,
    drum: 3,
  }

  return ids[bank]
}

function parseHitSample(rawHitSample = "0:0:0:0:") {
  const parts = rawHitSample.split(":")

  return {
    normalSet: Number(parts[0]) || 0,
    additionSet: Number(parts[1]) || 0,
    index: Number(parts[2]) || 0,
    volume: Number(parts[3]) || 0,
    filename: parts.slice(4).join(":"),
  }
}

function formatHitSample(hitSample: ReturnType<typeof parseHitSample>) {
  return [
    hitSample.normalSet,
    hitSample.additionSet,
    hitSample.index,
    hitSample.volume,
    hitSample.filename,
  ].join(":")
}

function applySampleToHitSample(rawHitSample: string | undefined, sample: ExportSample) {
  const hitSample = parseHitSample(rawHitSample)
  const sampleSetId = getSampleSetId(sample.bank)

  hitSample.filename = ""

  if (sample.sound === "hitnormal") {
    hitSample.normalSet = sampleSetId
  } else {
    hitSample.additionSet = sampleSetId
  }

  hitSample.index = sample.sampleIndex

  return formatHitSample(hitSample)
}

function chooseLayerSampleIndex(layer: HitsoundLayer) {
  const normal = layer.normal
  const addition = layer.addition

  if (!normal) {
    return addition?.sampleIndex ?? 0
  }

  if (!addition) {
    return normal.sampleIndex
  }

  // TODO: osu has only one custom sample index per hitSample. If normal and
  // addition layers use different custom indices, choose the higher track for
  // now and surface this as an export conflict later.
  return addition.trackIndex > normal.trackIndex ? addition.sampleIndex : normal.sampleIndex
}

function applyLayerToHitSample(rawHitSample: string | undefined, layer: HitsoundLayer) {
  const hitSample = parseHitSample(rawHitSample)

  hitSample.filename = ""

  if (layer.normal) {
    hitSample.normalSet = getSampleSetId(layer.normal.bank)
  }

  if (layer.addition) {
    hitSample.additionSet = getSampleSetId(layer.addition.bank)
  }

  hitSample.index = chooseLayerSampleIndex(layer)

  return formatHitSample(hitSample)
}

function getHitSamplePartIndex(kind: HitObjectKind) {
  if (kind === "slider") {
    return 10
  }

  if (kind === "spinner") {
    return 6
  }

  if (kind === "circle") {
    return 5
  }

  return -1
}

function applyHeadHitsound(parts: string[], kind: HitObjectKind, layer: HitsoundLayer) {
  parts[4] = String(layer.hitSoundBits)

  const hitSamplePartIndex = getHitSamplePartIndex(kind)

  if (hitSamplePartIndex >= 0) {
    parts[hitSamplePartIndex] = applyLayerToHitSample(parts[hitSamplePartIndex], layer)
    return
  }

  if (kind === "hold" && parts[5]) {
    const [endTime, ...rawHitSampleParts] = parts[5].split(":")
    const hitSample = applyLayerToHitSample(rawHitSampleParts.join(":"), layer)

    parts[5] = `${endTime}:${hitSample}`
  }
}

function normalizeSliderEdgeParts(parts: string[]) {
  const slides = Math.max(1, Number(parts[6]) || 1)
  const edgeCount = slides + 1
  const edgeSounds = (parts[8] || "").split("|").filter(Boolean)
  const edgeSets = (parts[9] || "").split("|").filter(Boolean)

  while (edgeSounds.length < edgeCount) {
    edgeSounds.push("0")
  }

  while (edgeSets.length < edgeCount) {
    edgeSets.push("0:0")
  }

  parts[8] = edgeSounds.join("|")
  parts[9] = edgeSets.join("|")

  if (parts.length <= 10) {
    parts[10] = parts[10] ?? "0:0:0:0:"
  }

  return { edgeSounds, edgeSets }
}

function formatEdgeSet(layer: HitsoundLayer) {
  const normalSet = layer.normal ? getSampleSetId(layer.normal.bank) : 0
  const additionSet = layer.addition ? getSampleSetId(layer.addition.bank) : 0

  return `${normalSet}:${additionSet}`
}

function applySliderEdgeHitsound(
  parts: string[],
  layer: HitsoundLayer,
  edge: "head" | "end",
) {
  const { edgeSounds, edgeSets } = normalizeSliderEdgeParts(parts)
  const edgeIndex = edge === "head" ? 0 : edgeSounds.length - 1

  edgeSounds[edgeIndex] = String(layer.hitSoundBits)
  edgeSets[edgeIndex] = formatEdgeSet(layer)
  parts[8] = edgeSounds.join("|")
  parts[9] = edgeSets.join("|")
  parts[10] = applyLayerToHitSample(parts[10], layer)
}

function mergeHitsoundLayers(
  left: HitsoundLayer | undefined,
  right: HitsoundLayer | undefined,
) {
  if (!left) {
    return right
  }

  if (!right) {
    return left
  }

  return {
    normal:
      right.normal && (!left.normal || right.normal.trackIndex > left.normal.trackIndex)
        ? right.normal
        : left.normal,
    addition:
      right.addition && (!left.addition || right.addition.trackIndex > left.addition.trackIndex)
        ? right.addition
        : left.addition,
    hitSoundBits: left.hitSoundBits | right.hitSoundBits,
  }
}

function rewriteHitObjectLine(line: string, assignment: SourceHitsoundAssignment) {
  const parts = line.split(",")
  const kind = getObjectKind(Number(parts[3]))

  if (kind === "slider") {
    const sliderBodyWhistle =
      assignment.sliderBody?.addition?.sound === "sliderwhistle" ? assignment.sliderBody : undefined
    const sliderHeadLayer = mergeHitsoundLayers(
      assignment.head,
      sliderBodyWhistle,
    )

    if (sliderHeadLayer) {
      applyHeadHitsound(parts, kind, sliderHeadLayer)
      applySliderEdgeHitsound(parts, sliderHeadLayer, "head")
    }

    if (assignment.sliderEnd) {
      applySliderEdgeHitsound(parts, assignment.sliderEnd, "end")
    }
  } else if (assignment.head) {
    applyHeadHitsound(parts, kind, assignment.head)
  }

  return parts.join(",")
}

function buildHitsoundedOsuText() {
  if (!originalOsuText.value || !hitObjectLineIndices.value.length) {
    return ""
  }

  const lines = originalOsuText.value.split(/\r?\n/)
  const assignments = buildSourceHitsoundAssignments()

  for (const [sourceIndex, assignment] of assignments.entries()) {
    const lineIndex = hitObjectLineIndices.value[sourceIndex]

    if (lineIndex === undefined || !lines[lineIndex]) {
      continue
    }

    lines[lineIndex] = rewriteHitObjectLine(lines[lineIndex], assignment)
  }

  return lines.join("\n")
}

function getUsedExportSamples() {
  const samplesByFileName = new Map<string, ExportSample>()

  if (notes.value.length) {
    const fallbackSample = getFallbackExportSample()

    if (fallbackSample.data) {
      samplesByFileName.set(fallbackSample.fileName, fallbackSample)
    }
  }

  tracks.value.forEach((track, trackIndex) => {
    if (!track.hits.some(Boolean)) {
      return
    }

    const sample = getExportSampleForTrack(track, trackIndex)

    if (!sample) {
      return
    }

    // TODO: Surface duplicate export filenames in the UI. For now, later
    // tracks overwrite earlier tracks, matching the hitsound conflict rule.
    if (sample.data) {
      samplesByFileName.set(sample.fileName, sample)
    }
  })

  return [...samplesByFileName.values()]
}

async function addSampleToZip(zip: InstanceType<typeof import("jszip").default>, sample: ExportSample) {
  if (sample.data) {
    zip.file(sample.fileName, sample.data)
  }
}

async function downloadHitsoundedOsu() {
  const hitsoundedOsuText = buildHitsoundedOsuText()

  if (!hitsoundedOsuText) {
    return
  }

  const { default: JSZip } = await import("jszip")
  const zip = new JSZip()
  const baseName = originalOsuFileName.value.replace(/\.osu$/i, "") || "beatmap"

  zip.file(`${baseName} [hitsounded].osu`, hitsoundedOsuText)

  for (const sample of getUsedExportSamples()) {
    await addSampleToZip(zip, sample)
  }

  const blob = await zip.generateAsync({ type: "blob" })
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")

  link.href = url
  link.download = `${baseName} [hitsounded].zip`
  link.click()
  URL.revokeObjectURL(url)
}

function toggleHit(trackIndex: number, noteIndex: number) {
  const track = tracks.value[trackIndex]

  if (!track) {
    return
  }

  activeTrackIndex.value = trackIndex
  track.hits[noteIndex] = !track.hits[noteIndex]
}

function setActiveTrack(trackIndex: number) {
  if (!tracks.value[trackIndex]) {
    return
  }

  activeTrackIndex.value = trackIndex
}

function noteDisplayTime(note: OsuNote) {
  return displayTimeMs(note)
}

function findNearestNoteTime(timeMs: number) {
  let nearestTime = timeMs
  let nearestDistance = Number.POSITIVE_INFINITY

  for (const note of notes.value) {
    const candidateTime = noteDisplayTime(note)
    const distance = Math.abs(candidateTime - timeMs)

    if (distance < nearestDistance) {
      nearestDistance = distance
      nearestTime = candidateTime
    }
  }

  return nearestTime
}

function findNoteIndexAtTime(timeMs: number) {
  let nearestIndex = -1
  let nearestDistance = Number.POSITIVE_INFINITY
  const toleranceMs = 3

  for (const note of notes.value) {
    const distance = Math.abs(noteDisplayTime(note) - timeMs)

    if (distance < nearestDistance) {
      nearestDistance = distance
      nearestIndex = note.index
    }
  }

  return nearestDistance <= toleranceMs ? nearestIndex : -1
}

function selectionRangeStyle() {
  const startX = timeToPixel(selectionStartMs.value)
  const endX = timeToPixel(selectionEndMs.value)

  return {
    left: `${startX}px`,
    width: `${Math.max(1, endX - startX)}px`,
  }
}

function startRangeSelection(event: PointerEvent, trackIndex: number) {
  const target = event.target as HTMLElement | null

  if (event.button !== 0) {
    return
  }

  if (target?.closest("button, input, label, audio, .lane-label")) {
    return
  }

  const timeMs = findNearestNoteTime(getTimelineTimeFromClientX(event.clientX))

  setActiveTrack(trackIndex)
  selectionTrackIndex.value = trackIndex
  selectionAnchorMs.value = timeMs
  selectionFocusMs.value = timeMs
  isSelectingRange.value = true
  suppressNextTimelineClick.value = true
  event.preventDefault()
}

function updateRangeSelection(event: PointerEvent) {
  if (!isSelectingRange.value) {
    return
  }

  selectionFocusMs.value = findNearestNoteTime(getTimelineTimeFromClientX(event.clientX))
}

function finishRangeSelection() {
  if (!isSelectingRange.value) {
    return
  }

  isSelectingRange.value = false

  if (selectionDurationMs.value <= 0) {
    selectionTrackIndex.value = null
    selectionAnchorMs.value = null
    selectionFocusMs.value = null
    suppressNextTimelineClick.value = false
    clipboardStatus.value = ""
    return
  }

  clipboardStatus.value = hasSelection.value
    ? `Selected ${formatTime(selectionStartMs.value)}-${formatTime(selectionEndMs.value)} on ${
        tracks.value[selectionTrackIndex.value ?? 0]?.name ?? "track"
      }.`
    : ""
}

function clearSelection() {
  selectionTrackIndex.value = null
  selectionAnchorMs.value = null
  selectionFocusMs.value = null
  isSelectingRange.value = false
  suppressNextTimelineClick.value = false
  clipboardStatus.value = "Selection cleared."
}

function copySelection() {
  if (!hasSelection.value || selectionTrackIndex.value === null) {
    clipboardStatus.value = "Drag across a track lane to select a pattern first."
    return
  }

  const sourceTrack = tracks.value[selectionTrackIndex.value]

  if (!sourceTrack) {
    return
  }

  copiedPattern.value = {
    sourceTrackName: sourceTrack.name,
    durationMs: selectionDurationMs.value,
    hits: notes.value
      .filter((note) => {
        const timeMs = noteDisplayTime(note)

        return (
          timeMs >= selectionStartMs.value &&
          timeMs <= selectionEndMs.value &&
          sourceTrack.hits[note.index]
        )
      })
      .map((note) => ({
        offsetMs: noteDisplayTime(note) - selectionStartMs.value,
      })),
  }
  clipboardStatus.value = `Copied ${copiedPattern.value.hits.length} hits from ${sourceTrack.name}.`
}

function pasteSelection() {
  const pattern = copiedPattern.value
  const targetTrack = tracks.value[activeTrackIndex.value]

  if (!pattern || !targetTrack) {
    clipboardStatus.value = "Copy a selected pattern before pasting."
    return
  }

  const pasteStartMs = findNearestNoteTime(currentTimeMs.value)
  const pasteEndMs = pasteStartMs + pattern.durationMs

  for (const note of notes.value) {
    const timeMs = noteDisplayTime(note)

    if (timeMs >= pasteStartMs && timeMs <= pasteEndMs) {
      targetTrack.hits[note.index] = false
    }
  }

  let pastedCount = 0

  for (const copiedHit of pattern.hits) {
    const targetIndex = findNoteIndexAtTime(pasteStartMs + copiedHit.offsetMs)

    if (targetIndex === -1) {
      continue
    }

    targetTrack.hits[targetIndex] = true
    pastedCount += 1
  }

  clipboardStatus.value = `Pasted ${pastedCount} hits to ${targetTrack.name} at ${formatTime(pasteStartMs)}.`
}

function clearSelectedRegion() {
  if (!hasSelection.value || selectionTrackIndex.value === null) {
    clipboardStatus.value = "Drag across a track lane to select a region first."
    return
  }

  const track = tracks.value[selectionTrackIndex.value]

  if (!track) {
    return
  }

  let clearedCount = 0

  for (const note of notes.value) {
    const timeMs = noteDisplayTime(note)

    if (timeMs < selectionStartMs.value || timeMs > selectionEndMs.value || !track.hits[note.index]) {
      continue
    }

    track.hits[note.index] = false
    clearedCount += 1
  }

  clipboardStatus.value = `Cleared ${clearedCount} hits from ${track.name}.`
}

function isTypingTarget(target: EventTarget | null) {
  const element = target as HTMLElement | null

  return Boolean(
    element?.closest("input, textarea, select") ||
      element?.isContentEditable,
  )
}

function handleGlobalKeydown(event: KeyboardEvent) {
  if (isTypingTarget(event.target)) {
    return
  }

  const key = event.key.toLowerCase()

  if ((event.ctrlKey || event.metaKey) && key === "c") {
    event.preventDefault()
    copySelection()
    return
  }

  if ((event.ctrlKey || event.metaKey) && key === "v") {
    event.preventDefault()
    pasteSelection()
    return
  }

  if (event.key === "Delete") {
    event.preventDefault()
    clearSelectedRegion()
    return
  }

  if (event.key === "Escape") {
    event.preventDefault()
    clearSelection()
    return
  }

  if (event.code === "Space") {
    event.preventDefault()
    void togglePlayback()
    return
  }

  if (!event.ctrlKey && !event.metaKey && !event.altKey && key === "z") {
    event.preventDefault()
    void resetPlaybackAnchorToBeginning()
  }
}

async function togglePlayback() {
  if (isPlaying.value) {
    stopPlayback()
    return
  }

  await startPlayback()
}

async function startPlayback() {
  await startPlaybackFrom(playbackAnchorMs.value)
}

async function startPlaybackFrom(startTimeMs: number) {
  if (!canPlay.value) {
    return
  }

  const toneApi = await ensureTone()

  stopPlayback()
  await toneApi.start()

  try {
    await rebuildPlayers(toneApi)
  } catch (error) {
    // Keep transport/backing playback working even if one or more samples fail to load.
    console.error("Failed to load one or more sample players.", error)
  }

  const transport = toneApi.Transport
  const leadInSeconds = 0.08
  const startSeconds = startTimeMs / 1_000

  transport.cancel(0)
  transport.stop()
  transport.position = startSeconds

  for (const track of tracks.value) {
    const player = players.get(track.id)

    if (!player) {
      continue
    }

    track.hits.forEach((enabled, noteIndex) => {
      const note = notes.value[noteIndex]

      if (!enabled || !note) {
        return
      }

      const scheduledTimeMs = snapPlaybackToGrid.value
        ? getSnappedTimeMs(note.timeMs)
        : note.timeMs

      if (scheduledTimeMs < startTimeMs - 1) {
        return
      }

      const scheduledSeconds = Math.max(0, (scheduledTimeMs + audioOffsetMs.value) / 1_000)

      transport.scheduleOnce((time) => {
        player.start(time)
      }, scheduledSeconds)
    })
  }

  if (backingAudio.value && backingAudioUrl.value) {
    backingAudio.value.pause()
    backingAudio.value.currentTime = startSeconds
    backingStartTimeoutId = window.setTimeout(() => {
      void backingAudio.value?.play()
    }, leadInSeconds * 1_000)
  }

  currentTimeMs.value = startTimeMs
  isPlaying.value = true
  transport.start(`+${leadInSeconds}`, startSeconds)
  updatePlayhead()
}

function stopPlayback(resetPlayhead = true) {
  if (backingStartTimeoutId !== null) {
    window.clearTimeout(backingStartTimeoutId)
    backingStartTimeoutId = null
  }

  if (animationFrameId !== null) {
    window.cancelAnimationFrame(animationFrameId)
    animationFrameId = null
  }

  if (tone) {
    tone.Transport.stop()
    tone.Transport.cancel(0)

    for (const player of players.values()) {
      player.stop()
    }
  }

  if (backingAudio.value) {
    backingAudio.value.pause()

    if (resetPlayhead) {
      backingAudio.value.currentTime = playbackAnchorMs.value / 1_000
    }
  }

  if (resetPlayhead) {
    currentTimeMs.value = playbackAnchorMs.value
  }

  isPlaying.value = false
}

async function ensureTone() {
  if (!tone) {
    tone = await import("tone")
  }

  return tone
}

async function rebuildPlayers(toneApi: ToneNamespace) {
  for (const player of players.values()) {
    player.dispose()
  }

  players = new Map()

  for (const track of tracks.value) {
    if (!track.sampleUrl) {
      continue
    }

    players.set(track.id, new toneApi.Player(track.sampleUrl).toDestination())
  }

  if (players.size > 0) {
    await toneApi.loaded()
  }
}

function updatePlayhead() {
  if (!isPlaying.value) {
    return
  }

  if (backingAudio.value && backingAudioUrl.value && !backingAudio.value.paused) {
    currentTimeMs.value = backingAudio.value.currentTime * 1_000
  } else if (tone) {
    currentTimeMs.value = tone.Transport.seconds * 1_000
  }

  followPlayheadInTimeline()

  if (durationMs.value > 0 && currentTimeMs.value > durationMs.value + 500) {
    stopPlayback()
    return
  }

  animationFrameId = window.requestAnimationFrame(updatePlayhead)
}

function getSnappedTimeMs(timeMs: number) {
  const timingPoint = getTimingPointAt(timeMs)

  if (!timingPoint) {
    return timeMs
  }

  const stepMs = timingPoint.beatLengthMs / snapDivisor.value

  if (stepMs <= 0) {
    return timeMs
  }

  return timingPoint.timeMs + Math.round((timeMs - timingPoint.timeMs) / stepMs) * stepMs
}

function getTimingPointAt(timeMs: number) {
  if (!timingPoints.value.length) {
    return null
  }

  let activeTimingPoint = timingPoints.value[0]

  for (const timingPoint of timingPoints.value) {
    if (timingPoint.timeMs > timeMs) {
      break
    }

    activeTimingPoint = timingPoint
  }

  return activeTimingPoint
}

function displayTimeMs(note: OsuNote) {
  return snapPlaybackToGrid.value ? getSnappedTimeMs(note.timeMs) : note.timeMs
}

function timeToPixel(timeMs: number) {
  const displayMs = Math.max(0, timeMs - timelineStartMs.value)

  return laneLabelWidth + (displayMs / 1_000) * pixelsPerSecond.value
}

function timeLeft(timeMs: number) {
  return `${timeToPixel(timeMs)}px`
}

function noteLeft(note: OsuNote) {
  return timeLeft(displayTimeMs(note))
}

function sliderBodyStyle(note: OsuNote) {
  const endSlot = sliderEndSlotsBySource.value.get(note.sourceIndex)
  const displayStartMs = snapPlaybackToGrid.value
    ? getSnappedTimeMs(note.sourceTimeMs)
    : note.sourceTimeMs
  const displayEndMs = endSlot ? displayTimeMs(endSlot) : displayTimeMs(note)
  const startX = timeToPixel(displayStartMs)
  const endX = Math.max(startX + 18, timeToPixel(displayEndMs))
  const bodyStartX = startX + markerDiameter / 2
  const bodyEndX = endX - markerDiameter / 2

  return {
    left: `${bodyStartX}px`,
    width: `${Math.max(2, bodyEndX - bodyStartX)}px`,
  }
}

function playheadLeft() {
  return timeLeft(currentTimeMs.value)
}

function isNearPlayhead(note: OsuNote) {
  return isPlaying.value && Math.abs(displayTimeMs(note) - currentTimeMs.value) < 80
}

function updateTimelineViewport() {
  const scroller = timelineScroll.value

  if (!scroller) {
    return
  }

  timelineScrollLeft.value = scroller.scrollLeft
  timelineViewportWidth.value = scroller.clientWidth
}

function getWheelDeltaMultiplier(event: WheelEvent) {
  return event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? timelineScroll.value?.clientWidth ?? 1 : 1
}

function clampZoom(value: number) {
  return Math.min(900, Math.max(60, value))
}

function zoomTimelineAtClientX(clientX: number, wheelDelta: number) {
  const scroller = timelineScroll.value

  if (!scroller) {
    return
  }

  const rect = scroller.getBoundingClientRect()
  const xInViewport = clientX - rect.left
  const xInContent = scroller.scrollLeft + xInViewport
  const timeAtCursorMs =
    timelineStartMs.value +
    (Math.max(0, xInContent - laneLabelWidth) / pixelsPerSecond.value) * 1_000
  const zoomFactor = Math.exp(-wheelDelta * 0.0015)
  const nextZoom = clampZoom(Math.round(pixelsPerSecond.value * zoomFactor))

  if (nextZoom === pixelsPerSecond.value) {
    return
  }

  pixelsPerSecond.value = nextZoom

  void nextTick(() => {
    const nextXInContent = timeToPixel(timeAtCursorMs)
    scroller.scrollLeft = Math.max(0, nextXInContent - xInViewport)
    updateTimelineViewport()
  })
}

function handleTimelineWheel(event: WheelEvent) {
  const scroller = timelineScroll.value

  if (!scroller) {
    return
  }

  event.preventDefault()

  const deltaModeMultiplier = getWheelDeltaMultiplier(event)

  if (event.ctrlKey) {
    zoomTimelineAtClientX(event.clientX, event.deltaY * deltaModeMultiplier)
    return
  }

  const target = event.target as HTMLElement | null

  if (target?.closest(".lane-label, .ruler-label")) {
    scroller.scrollTop += event.deltaY * deltaModeMultiplier
    scroller.scrollLeft += event.deltaX * deltaModeMultiplier
    updateTimelineViewport()
    return
  }

  const dominantDelta =
    Math.abs(event.deltaX) > Math.abs(event.deltaY) ? event.deltaX : event.deltaY

  scroller.scrollLeft += dominantDelta * deltaModeMultiplier
  updateTimelineViewport()
}

function startTimelinePan(event: PointerEvent) {
  const scroller = timelineScroll.value

  if (!scroller || event.button !== 2) {
    return
  }

  event.preventDefault()
  isPanningTimeline.value = true
  timelinePanPointerId = event.pointerId
  timelinePanStartX = event.clientX
  timelinePanStartY = event.clientY
  timelinePanStartScrollLeft = scroller.scrollLeft
  timelinePanStartScrollTop = scroller.scrollTop
  scroller.setPointerCapture(event.pointerId)
}

function updateTimelinePan(event: PointerEvent) {
  const scroller = timelineScroll.value

  if (!scroller || !isPanningTimeline.value || event.pointerId !== timelinePanPointerId) {
    return
  }

  event.preventDefault()
  scroller.scrollLeft = timelinePanStartScrollLeft - (event.clientX - timelinePanStartX)
  scroller.scrollTop = timelinePanStartScrollTop - (event.clientY - timelinePanStartY)
  updateTimelineViewport()
}

function finishTimelinePan(event: PointerEvent) {
  const scroller = timelineScroll.value

  if (!isPanningTimeline.value || event.pointerId !== timelinePanPointerId) {
    return
  }

  event.preventDefault()
  scroller?.releasePointerCapture(event.pointerId)
  isPanningTimeline.value = false
  timelinePanPointerId = null
}

function handleTimelinePointerMove(event: PointerEvent) {
  updateTimelinePan(event)
  updateRangeSelection(event)
}

function handleTimelinePointerUp(event: PointerEvent) {
  finishTimelinePan(event)
  finishRangeSelection()
}

function handleTimelinePointerLeave(event: PointerEvent) {
  if (isPanningTimeline.value) {
    finishTimelinePan(event)
  }

  finishRangeSelection()
}

function getTimelineTimeFromClientX(clientX: number) {
  const scroller = timelineScroll.value

  if (!scroller) {
    return currentTimeMs.value
  }

  const rect = scroller.getBoundingClientRect()
  const xInContent = scroller.scrollLeft + clientX - rect.left
  const timeMs =
    timelineStartMs.value +
    (Math.max(0, xInContent - laneLabelWidth) / pixelsPerSecond.value) * 1_000

  return Math.min(Math.max(timelineStartMs.value, timeMs), durationMs.value)
}

async function seekToTime(timeMs: number) {
  const clampedTimeMs = Math.min(Math.max(playbackStartMs.value, timeMs), durationMs.value)
  const wasPlaying = isPlaying.value

  playbackAnchorMs.value = clampedTimeMs
  stopPlayback(false)
  currentTimeMs.value = clampedTimeMs

  if (tone) {
    tone.Transport.position = clampedTimeMs / 1_000
  }

  if (backingAudio.value) {
    backingAudio.value.currentTime = clampedTimeMs / 1_000
  }

  centerPlayheadInTimeline()

  if (wasPlaying) {
    await startPlaybackFrom(clampedTimeMs)
  }
}

async function resetPlaybackAnchorToBeginning() {
  const startMs = playbackStartMs.value
  const wasPlaying = isPlaying.value

  playbackAnchorMs.value = startMs
  stopPlayback(false)
  currentTimeMs.value = startMs

  if (tone) {
    tone.Transport.position = startMs / 1_000
  }

  if (backingAudio.value) {
    backingAudio.value.currentTime = startMs / 1_000
  }

  centerPlayheadInTimeline()

  if (wasPlaying) {
    await startPlaybackFrom(startMs)
  }
}

function handleTimelineSeek(event: MouseEvent) {
  if (suppressNextTimelineClick.value) {
    suppressNextTimelineClick.value = false
    return
  }

  const target = event.target as HTMLElement | null

  if (target?.closest("button, input, label, audio")) {
    return
  }

  void seekToTime(getTimelineTimeFromClientX(event.clientX))
}

function centerPlayheadInTimeline() {
  const scroller = timelineScroll.value

  if (!scroller) {
    return
  }

  const playheadX = timeToPixel(currentTimeMs.value)
  scroller.scrollLeft = Math.max(0, playheadX - scroller.clientWidth / 2)
  updateTimelineViewport()
}

function followPlayheadInTimeline() {
  const scroller = timelineScroll.value

  if (!followPlayhead.value || !scroller) {
    return
  }

  centerPlayheadInTimeline()
}

function trackLaneStyle(trackIndex: number) {
  const color = trackPalette[trackIndex % trackPalette.length]

  return {
    "--track-accent": color.accent,
    "--track-accent-dark": color.accentDark,
    "--track-accent-muted": color.accentMuted,
    "--track-accent-soft": color.accentSoft,
  }
}

function trackHitCount(track: Track) {
  return track.hits.filter(Boolean).length
}

function formatTime(timeMs: number) {
  const totalSeconds = Math.max(0, Math.floor(timeMs / 1_000))
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = String(totalSeconds % 60).padStart(2, "0")

  return `${minutes}:${seconds}`
}

function formatSlotKind(kind: HitSlotKind) {
  const labels: Record<HitSlotKind, string> = {
    circle: "circle",
    hold: "hold",
    slider: "slider head",
    "slider-body": "slider body",
    "slider-end": "slider end",
    spinner: "spinner",
  }

  return labels[kind]
}

function formatNumber(value: number) {
  return Number.isInteger(value) ? String(value) : value.toFixed(2)
}

onMounted(() => {
  window.addEventListener("keydown", handleGlobalKeydown)
})

onBeforeUnmount(() => {
  window.removeEventListener("keydown", handleGlobalKeydown)
  stopPlayback()

  for (const player of players.values()) {
    player.dispose()
  }

  for (const track of tracks.value) {
    revokeCustomSample(track)
  }

  if (backingAudioUrl.value) {
    URL.revokeObjectURL(backingAudioUrl.value)
  }

})
</script>

<template>
  <main class="app-shell">
    <section class="panel upload-panel">
      <div class="upload-summary">
        <div>
          <p class="eyebrow">hitsound daw</p>
          <h1>{{ mapInfo ? mapTitle : "Place sounds on osu notes" }}</h1>
        </div>
        <p v-if="mapInfo">
          {{ notes.length }} hitsound slots, timeline starts at
          <code>{{ formatTime(timelineStartMs) }}</code>. {{ timingSummary }}.
        </p>
        <p v-else>
          Upload a beatmap and backing audio, then assign samples on the
          timeline.
        </p>
      </div>

      <div class="compact-uploads">
        <label class="compact-upload">
          <span>.osu map</span>
          <input accept=".osu,text/plain" type="file" @change="handleOsuUpload" />
        </label>

        <label class="compact-upload">
          <span>Backing audio</span>
          <input accept="audio/*" type="file" @change="handleBackingUpload" />
        </label>

        <label class="compact-upload">
          <span>Fallback soft-hitnormal</span>
          <input accept="audio/*" type="file" @change="handleFallbackSampleUpload" />
        </label>

        <label class="compact-upload">
          <span>Load project</span>
          <input accept=".json,application/json" type="file" @change="handleProjectLoad" />
        </label>

        <button
          class="ghost-button export-button"
          type="button"
          :disabled="!originalOsuText"
          @click="saveProject"
        >
          Save project
        </button>

        <button
          class="ghost-button export-button"
          type="button"
          :disabled="!notes.length"
          @click="downloadHitsoundedOsu"
        >
          Download hitsounded ZIP
        </button>
      </div>

      <p v-if="mapInfo?.audioFilename" class="hint upload-hint">
        Referenced audio: <code>{{ mapInfo.audioFilename }}</code>
        <span v-if="backingAudioName"> Loaded: {{ backingAudioName }}</span>
        <span v-if="fallbackCustomSample">
          Fallback sample: {{ fallbackCustomSample.originalName }} as soft-hitnormal.wav
        </span>
      </p>

      <audio
        v-if="backingAudioUrl"
        ref="backingAudio"
        class="backing-player"
        controls
        :src="backingAudioUrl"
        @ended="stopPlayback()"
        @loadedmetadata="handleBackingMetadata"
      />
    </section>

    <section v-if="notes.length" class="panel daw-panel">
      <div class="transport">
        <button class="play-button" type="button" :disabled="!canPlay" @click="togglePlayback">
          {{ isPlaying ? "Stop" : "Play" }}
        </button>

        <div class="stat">
          <span>Playhead</span>
          <strong>{{ formatTime(currentTimeMs) }}</strong>
        </div>

        <div class="stat">
          <span>Start point</span>
          <strong>{{ formatTime(playbackAnchorMs) }}</strong>
        </div>

        <div class="stat">
          <span>Placed hits</span>
          <strong>{{ selectedHitsCount }}</strong>
        </div>

        <div class="stat">
          <span>Snap grid</span>
          <strong>1/{{ snapDivisor }}</strong>
        </div>

        <label class="compact-control">
          <span>Sample offset ms</span>
          <input v-model.number="audioOffsetMs" type="number" step="5" />
        </label>

        <label class="compact-control checkbox-control">
          <span>Playback snapping</span>
          <input v-model="snapPlaybackToGrid" type="checkbox" />
        </label>

        <label class="compact-control checkbox-control">
          <span>Follow playhead</span>
          <input v-model="followPlayhead" type="checkbox" />
        </label>

        <div class="clipboard-controls">
          <button type="button" :disabled="!hasSelection" @click="copySelection">Copy selection</button>
          <button type="button" :disabled="!copiedPattern" @click="pasteSelection">Paste at playhead</button>
          <span>{{ clipboardStatus || `Target: ${tracks[activeTrackIndex]?.name ?? "track"}` }}</span>
        </div>

        <label class="compact-control">
          <span>Zoom</span>
          <input
            v-model.number="pixelsPerSecond"
            max="900"
            min="60"
            type="range"
            @input="updateTimelineViewport"
          />
        </label>
      </div>

      <div
        ref="timelineScroll"
        class="timeline-scroll"
        :class="{ panning: isPanningTimeline }"
        @click="handleTimelineSeek"
        @contextmenu.prevent
        @pointerdown="startTimelinePan"
        @pointermove="handleTimelinePointerMove"
        @pointerup="handleTimelinePointerUp"
        @pointerleave="handleTimelinePointerLeave"
        @scroll="updateTimelineViewport"
        @wheel="handleTimelineWheel"
      >
        <div
          class="timeline-content"
          :style="{ width: timelineWidth, '--second-width': `${pixelsPerSecond}px` }"
        >
          <div class="ruler">
            <span class="ruler-label">Time</span>
            <span
              v-for="note in rulerNotes"
              :key="`ruler-${note.id}`"
              class="ruler-note"
              :style="{ left: noteLeft(note) }"
            >
              {{ formatTime(note.timeMs) }}
            </span>
          </div>

          <div class="snap-layer" aria-hidden="true">
            <span
              v-for="line in visibleSnapLines"
              :key="line.id"
              class="snap-line"
              :class="line.kind"
              :style="{ left: timeLeft(line.timeMs) }"
            />
          </div>

          <div class="playhead" :style="{ left: playheadLeft() }" />

          <div
            v-for="(track, trackIndex) in tracks"
            :key="track.id"
            class="track-lane"
            :class="{ active: trackIndex === activeTrackIndex }"
            :style="trackLaneStyle(trackIndex)"
            @pointerdown="startRangeSelection($event, trackIndex)"
          >
            <div class="lane-label" @click.stop="setActiveTrack(trackIndex)">
              <strong>{{ track.name }}</strong>
              <span>{{ track.sampleName }}</span>
            </div>

            <div
              v-if="hasSelection && selectionTrackIndex === trackIndex"
              class="selection-range"
              :style="selectionRangeStyle()"
            />

            <button
              v-for="note in visibleSliderBodySlots"
              :key="`${track.id}-${note.id}-body`"
              class="slider-body-strip"
              :class="{
                selected: track.hits[note.index],
                active: isNearPlayhead(note),
              }"
              :style="sliderBodyStyle(note)"
              type="button"
              :title="`${track.name} at ${formatTime(displayTimeMs(note))} (${formatSlotKind(note.kind)}, original ${formatTime(note.timeMs)}, source ${formatTime(note.sourceTimeMs)}, x:${note.x}, y:${note.y})`"
              @click.stop="toggleHit(trackIndex, note.index)"
            />

            <button
              v-for="note in visibleMarkerSlots"
              :key="`${track.id}-${note.id}`"
              class="note-cell"
              :class="{
                selected: track.hits[note.index],
                active: isNearPlayhead(note),
              }"
              :style="{ left: noteLeft(note) }"
              type="button"
              :title="`${track.name} at ${formatTime(displayTimeMs(note))} (${formatSlotKind(note.kind)}, original ${formatTime(note.timeMs)}, source ${formatTime(note.sourceTimeMs)}, x:${note.x}, y:${note.y})`"
              @click.stop="toggleHit(trackIndex, note.index)"
            />
          </div>
        </div>
      </div>
    </section>

    <section
      v-if="notes.length"
      class="panel track-panel"
      :class="{ collapsed: !isTrackDrawerOpen }"
    >
      <div class="section-heading track-drawer-heading">
        <div>
          <p class="eyebrow">Tracks</p>
          <h2>Assign samples</h2>
        </div>
        <div class="track-drawer-actions">
          <span>{{ tracks.length }} tracks</span>
          <button class="ghost-button" type="button" @click="addTrack">Add track</button>
          <button class="ghost-button" type="button" @click="isTrackDrawerOpen = !isTrackDrawerOpen">
            {{ isTrackDrawerOpen ? "Hide" : "Show" }}
          </button>
        </div>
      </div>

      <div v-show="isTrackDrawerOpen" class="track-list">
        <article
          v-for="(track, trackIndex) in tracks"
          :key="track.id"
          class="track-card"
          :class="{ active: trackIndex === activeTrackIndex }"
          @click="setActiveTrack(trackIndex)"
        >
          <input v-model="track.name" class="track-name" aria-label="Track name" />
          <p>{{ trackHitCount(track) }} hits</p>
          <label>
            <span>Default sample</span>
            <select
              :value="track.sampleSource === 'default' ? track.sampleUrl : ''"
              @change="handleDefaultSampleChange($event, trackIndex)"
            >
              <option value="" disabled>Choose default</option>
              <option v-for="sample in defaultSamples" :key="sample.url" :value="sample.url">
                {{ sample.name }}
              </option>
            </select>
          </label>
          <label>
            <span>Custom set</span>
            <input
              v-model.number="track.customSampleIndex"
              min="1"
              step="1"
              type="number"
              @change="handleCustomSampleIndexChange(trackIndex)"
            />
          </label>
          <label>
            <span>Custom type</span>
            <select
              :value="`${track.customSampleBank}-${track.customSampleSound}`"
              @change="handleCustomSampleTypeChange($event, trackIndex)"
            >
              <option v-for="sampleType in sampleTypeOptions" :key="sampleType.label" :value="sampleType.label">
                {{ sampleType.label }}
              </option>
            </select>
          </label>
          <label>
            <span>Custom sample</span>
            <input accept="audio/*" type="file" @change="handleSampleUpload($event, trackIndex)" />
          </label>
          <strong>{{ track.sampleName }}</strong>
          <div class="track-actions">
            <button type="button" @click="clearTrack(trackIndex)">Clear</button>
            <button type="button" @click="removeTrack(trackIndex)">Remove</button>
          </div>
        </article>
      </div>
    </section>

    <section v-if="!notes.length" class="panel empty-panel">
      <h2>Start with an osu file</h2>
      <p>
        Once loaded, circles and slider parts become clickable timeline slots on
        each sample track.
      </p>
    </section>
  </main>
</template>

<style scoped>
:global(html),
:global(body),
:global(#__nuxt) {
  height: 100%;
}

:global(body) {
  margin: 0;
  overflow: hidden;
  background: #0f172a;
}

:global(*) {
  box-sizing: border-box;
}

.app-shell {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 100vh;
  overflow: hidden;
  padding: 16px;
  font-family:
    Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI",
    sans-serif;
  color: #e2e8f0;
  background:
    radial-gradient(circle at top left, rgba(34, 211, 238, 0.18), transparent 34rem),
    radial-gradient(circle at top right, rgba(168, 85, 247, 0.16), transparent 28rem),
    #0f172a;
}

.panel {
  margin: 0 auto;
  padding: 24px;
  width: min(1360px, 100%);
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 24px;
  background: rgba(15, 23, 42, 0.78);
  box-shadow: 0 24px 80px rgba(2, 6, 23, 0.28);
}

.upload-panel,
.section-heading,
.transport {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
}

.upload-panel h1,
.track-panel h2,
.empty-panel h2 {
  margin: 0;
  color: #f8fafc;
}

.upload-panel {
  align-items: flex-start;
  flex-wrap: wrap;
  flex: 0 0 auto;
  padding: 12px 14px;
}

.upload-summary {
  display: grid;
  gap: 4px;
  min-width: min(540px, 100%);
}

.upload-summary h1 {
  max-width: 760px;
  font-size: clamp(1.1rem, 2.2vw, 1.55rem);
  line-height: 1.05;
}

.upload-summary p,
.empty-panel p {
  max-width: 760px;
  margin: 0;
  color: #94a3b8;
  font-size: 0.92rem;
  line-height: 1.5;
}

.eyebrow {
  margin: 0 0 8px;
  color: #22d3ee;
  font-size: 0.75rem;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

code {
  color: #67e8f9;
}

button,
input,
select {
  font: inherit;
}

button {
  cursor: pointer;
}

button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.compact-uploads {
  display: flex;
  align-items: end;
  flex-wrap: wrap;
  gap: 10px;
}

.compact-upload {
  display: grid;
  gap: 6px;
  min-width: 160px;
  padding: 10px 12px;
  border: 1px dashed rgba(103, 232, 249, 0.55);
  border-radius: 14px;
  color: #cffafe;
  background: rgba(8, 47, 73, 0.55);
}

.compact-upload span,
.compact-control span,
.stat span,
.track-card span,
.lane-label span {
  color: #94a3b8;
  font-size: 0.8rem;
}

.compact-upload input {
  max-width: 170px;
  font-size: 0.78rem;
}

.hint {
  color: #cbd5e1;
}

.upload-hint {
  flex-basis: 100%;
  margin: -10px 0 0;
  font-size: 0.85rem;
}

.backing-player {
  flex-basis: 100%;
  width: min(360px, 100%);
  height: 34px;
}

.track-list {
  display: flex;
  gap: 10px;
  margin-top: 10px;
  overflow-x: auto;
  overflow-y: hidden;
  padding: 2px 2px 8px;
  scrollbar-width: thin;
}

.track-card {
  display: grid;
  flex: 0 0 860px;
  grid-template-columns: 112px 52px minmax(138px, 1fr) 72px minmax(138px, 1fr) 128px minmax(116px, 0.8fr) auto;
  align-items: end;
  gap: 8px;
  padding: 10px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 14px;
  background: rgba(30, 41, 59, 0.64);
  cursor: pointer;
}

.track-card.active {
  border-color: #67e8f9;
  box-shadow: 0 0 0 2px rgba(34, 211, 238, 0.18);
}

.track-card p,
.track-card strong {
  overflow: hidden;
  margin: 0;
  color: #cbd5e1;
  font-size: 0.82rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.track-card label {
  display: grid;
  gap: 4px;
}

.track-name,
.compact-control input,
.track-card select,
.track-card input[type="number"] {
  width: 100%;
  border: 1px solid rgba(148, 163, 184, 0.28);
  border-radius: 10px;
  padding: 7px 9px;
  color: #f8fafc;
  background: rgba(15, 23, 42, 0.85);
}

.track-card input[type="file"] {
  max-width: 130px;
  color: #cbd5e1;
  font-size: 0.72rem;
}

.track-actions {
  display: flex;
  gap: 8px;
}

.ghost-button,
.track-actions button,
.clipboard-controls button {
  border: 1px solid rgba(148, 163, 184, 0.28);
  border-radius: 999px;
  padding: 7px 11px;
  color: #e2e8f0;
  background: rgba(15, 23, 42, 0.8);
}

.daw-panel {
  display: flex;
  flex-direction: column;
  flex: 1 1 auto;
  min-height: 0;
  width: 100vw;
  max-width: none;
  margin-right: calc(50% - 50vw);
  margin-left: calc(50% - 50vw);
  padding: 14px 16px;
  border-radius: 0;
  overflow: hidden;
}

.track-panel {
  position: fixed;
  right: 16px;
  bottom: 12px;
  left: 16px;
  z-index: 20;
  width: auto;
  max-height: 38vh;
  padding: 10px 12px;
  border-radius: 16px;
  background: rgba(15, 23, 42, 0.96);
  backdrop-filter: blur(16px);
  transition: transform 160ms ease;
}

.track-panel.collapsed {
  transform: translateY(calc(100% - 46px));
}

.track-drawer-heading {
  gap: 12px;
}

.track-drawer-heading .eyebrow {
  margin-bottom: 2px;
}

.track-drawer-heading h2 {
  font-size: 1rem;
}

.track-drawer-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.track-drawer-actions span {
  color: #94a3b8;
  font-size: 0.8rem;
}

.transport {
  flex-wrap: wrap;
  flex: 0 0 auto;
  margin-bottom: 12px;
}

.play-button {
  border: 0;
  border-radius: 999px;
  padding: 13px 24px;
  color: #082f49;
  font-weight: 800;
  background: linear-gradient(135deg, #67e8f9, #c4b5fd);
}

.stat,
.compact-control {
  display: grid;
  gap: 4px;
}

.stat strong {
  color: #f8fafc;
  font-size: 1.15rem;
}

.compact-control {
  min-width: 150px;
}

.clipboard-controls {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  max-width: 520px;
}

.clipboard-controls span {
  color: #94a3b8;
  font-size: 0.8rem;
}

.checkbox-control input {
  width: 20px;
  height: 20px;
  accent-color: #22d3ee;
}

.timeline-scroll {
  flex: 1;
  overflow: auto;
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 18px;
  background: rgba(2, 6, 23, 0.45);
  cursor: default;
  scrollbar-width: none;
  -ms-overflow-style: none;
  overscroll-behavior: contain;
}

.timeline-scroll.panning {
  cursor: grabbing;
  user-select: none;
}

.timeline-scroll::-webkit-scrollbar {
  display: none;
}

.timeline-content {
  position: relative;
  min-width: 100%;
  padding-bottom: 14px;
}

.ruler {
  position: sticky;
  top: 0;
  z-index: 5;
  height: 44px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.18);
  background:
    linear-gradient(90deg, rgba(15, 23, 42, 0.98), rgba(15, 23, 42, 0.88)),
    repeating-linear-gradient(
      90deg,
      transparent 0 calc(var(--second-width) - 1px),
      rgba(148, 163, 184, 0.16) calc(var(--second-width) - 1px) var(--second-width)
    );
}

.ruler-label,
.lane-label {
  position: sticky;
  left: 0;
  z-index: 3;
  width: 190px;
}

.ruler-label {
  display: grid;
  height: 44px;
  place-items: center start;
  padding-left: 18px;
  color: #cbd5e1;
  font-weight: 800;
  background: rgba(15, 23, 42, 0.96);
}

.ruler-note {
  position: absolute;
  top: 14px;
  transform: translateX(-50%);
  color: #94a3b8;
  font-size: 0.72rem;
  white-space: nowrap;
}

.snap-layer {
  position: absolute;
  top: 44px;
  right: 0;
  bottom: 14px;
  left: 0;
  z-index: 2;
  pointer-events: none;
}

.snap-line {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 1px;
  background: rgba(148, 163, 184, 0.11);
}

.snap-line.beat {
  background: rgba(103, 232, 249, 0.22);
}

.snap-line.measure {
  width: 2px;
  background: rgba(249, 115, 22, 0.38);
}

.track-lane {
  position: relative;
  z-index: 1;
  height: 74px;
  border-bottom: 1px solid var(--track-accent-soft, rgba(148, 163, 184, 0.14));
  background:
    linear-gradient(90deg, var(--track-accent-soft, transparent), transparent 34rem),
    repeating-linear-gradient(
      90deg,
      transparent 0 calc(var(--second-width) - 1px),
      rgba(148, 163, 184, 0.1) calc(var(--second-width) - 1px) var(--second-width)
    );
}

.track-lane:last-child {
  border-bottom: 0;
}

.track-lane.active {
  box-shadow: inset 0 0 0 2px var(--track-accent-muted, rgba(103, 232, 249, 0.26));
}

.lane-label {
  display: grid;
  align-content: center;
  z-index: 8;
  height: 74px;
  padding: 0 16px;
  border-right: 2px solid var(--track-accent, rgba(148, 163, 184, 0.18));
  background:
    linear-gradient(90deg, var(--track-accent-soft, transparent), transparent),
    rgba(15, 23, 42, 0.98);
  box-shadow: 12px 0 18px rgba(2, 6, 23, 0.32);
  cursor: pointer;
}

.lane-label strong,
.lane-label span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.lane-label strong {
  color: var(--track-accent, #f8fafc);
}

.selection-range {
  position: absolute;
  top: 8px;
  bottom: 8px;
  z-index: 2;
  border: 1px solid var(--track-accent, #67e8f9);
  background: var(--track-accent-soft, rgba(103, 232, 249, 0.14));
  pointer-events: none;
}

.slider-body-strip {
  position: absolute;
  top: 50%;
  z-index: 2;
  height: 14px;
  transform: translateY(-50%);
  border: 1px solid var(--track-accent-muted, rgba(148, 163, 184, 0.45));
  border-radius: 0;
  background: rgba(51, 65, 85, 0.92);
}

.slider-body-strip:hover,
.slider-body-strip.active {
  border-color: var(--track-accent, #67e8f9);
  box-shadow: 0 0 0 3px var(--track-accent-soft, rgba(103, 232, 249, 0.12));
}

.slider-body-strip.selected {
  border-color: var(--track-accent, #22d3ee);
  background: linear-gradient(
    90deg,
    var(--track-accent-dark, #0891b2),
    var(--track-accent, #67e8f9),
    var(--track-accent-dark, #0891b2)
  );
}

.note-cell {
  position: absolute;
  top: 50%;
  z-index: 3;
  width: 22px;
  height: 22px;
  transform: translate(-50%, -50%);
  border: 1px solid var(--track-accent-muted, rgba(148, 163, 184, 0.35));
  border-radius: 50%;
  background: rgba(51, 65, 85, 0.9);
}

.note-cell:hover,
.note-cell.active {
  border-color: var(--track-accent, #67e8f9);
  box-shadow: 0 0 0 4px var(--track-accent-soft, rgba(103, 232, 249, 0.14));
}

.note-cell.selected {
  border-color: var(--track-accent, #22d3ee);
  background: linear-gradient(
    180deg,
    var(--track-accent, #67e8f9),
    var(--track-accent-dark, #0891b2)
  );
}

.playhead {
  position: absolute;
  top: 44px;
  bottom: 0;
  z-index: 4;
  width: 2px;
  background: #f97316;
  box-shadow: 0 0 18px rgba(249, 115, 22, 0.75);
  pointer-events: none;
}

.empty-panel {
  text-align: center;
}

@media (max-width: 760px) {
  .app-shell {
    padding: 16px;
  }

  .upload-panel,
  .compact-uploads {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
