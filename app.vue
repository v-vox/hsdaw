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
type HitSlotKind = HitObjectKind | "slider-body" | "slider-repeat" | "slider-end"
type SampleSource = "default" | "custom" | "none"
type HitsoundPickerMode = "default" | "custom"
type ChannelType = "regular" | "fx"
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
  edgeIndex?: number
  x: number
  y: number
  timeMs: number
  sourceTimeMs: number
  objectType: number
  kind: HitSlotKind
}

type Track = {
  id: number
  channelType: ChannelType
  collapsed: boolean
  name: string
  sampleName: string
  sampleUrl: string | null
  sampleSource: SampleSource
  customSampleBank: SampleBank
  customSampleSound: SampleSound
  customSampleIndex: number
  customSample: CustomSample | null
  regularNotes: RegularNote[]
  fxClips: FxClip[]
  hits: boolean[]
}

type RegularNote = {
  id: number
  startMs: number
  assignedNoteIndex: number | null
}

type FxClip = {
  id: number
  name: string
  bank: SampleBank
  sound: SampleSound
  sampleUrl: string
  mimeType: string
  data: ArrayBuffer
  startMs: number
  durationMs: number
  assignedNoteIndex: number | null
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
    trackOffset: number
  }>
}

type UndoTrackSnapshot = {
  trackId: number
  regularNotes: RegularNote[]
  fxClips: Array<Pick<FxClip, "id" | "bank" | "sound" | "startMs" | "durationMs" | "assignedNoteIndex">>
}

type UndoSnapshot = {
  tracks: UndoTrackSnapshot[]
  selectedRegularNoteIds: string[]
  activeTrackIndex: number
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
  additions?: ExportSample[]
  hitSoundBits: number
}

type SourceHitsoundAssignment = {
  head?: HitsoundLayer
  sliderBody?: HitsoundLayer
  sliderEnd?: HitsoundLayer
  sliderEdges?: Map<number, HitsoundLayer>
}

type ExportContext = {
  samplesByFileName: Map<string, ExportSample>
  fxSamplesByClipId: Map<number, ExportSample>
  occupiedCustomIndices: Map<string, Set<number>>
  mixedSamplesByKey: Map<string, ExportSample>
}

type SavedCustomSample = Omit<CustomSample, "data"> & {
  dataUrl: string
}

type SavedTrack = {
  channelType?: ChannelType
  collapsed?: boolean
  name: string
  sampleName: string
  sampleSource: SampleSource
  customSampleBank: SampleBank
  customSampleSound: SampleSound
  customSampleIndex: number
  customSample: SavedCustomSample | null
  regularNotes?: SavedRegularNote[]
  fxClips?: SavedFxClip[]
  hits: boolean[]
}

type SavedRegularNote = RegularNote

type SavedFxClip = Omit<FxClip, "data" | "sampleUrl"> & {
  dataUrl: string
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

const laneLabelWidth = 280
const timelineHeaderHeight = 82
const closedTrackLaneHeight = 82
const defaultPickerTrackLaneHeight = 280
const customPickerTrackLaneHeight = 310
const fxTrackLaneHeight = 82
const fxEditorTrackLaneHeight = 134
const guideSnapThresholdPx = 12
const markerDiameter = 22
const collapsedTrackLaneHeight = markerDiameter
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
const sampleBanks: SampleBank[] = ["soft", "normal", "drum"]
const sampleSounds: SampleSound[] = ["hitnormal", "hitclap", "hitfinish", "hitwhistle", "sliderwhistle"]
const maxUndoSnapshots = 60
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
const selectionAnchorTrackIndex = ref<number | null>(null)
const selectionFocusTrackIndex = ref<number | null>(null)
const isSelectingRange = ref(false)
const selectedRegularNoteIds = ref<Set<string>>(new Set())
const selectedFxClipId = ref<number | null>(null)
const copiedPattern = ref<CopiedPattern | null>(null)
const clipboardStatus = ref("")
const suppressNextTimelineClick = ref(false)
const isPanningTimeline = ref(false)
const fallbackCustomSample = ref<CustomSample | null>(null)
const hsPickerModes = ref<Record<number, HitsoundPickerMode>>({})
const hsPickerOpen = ref<Record<number, boolean>>({})
const undoStack: UndoSnapshot[] = []

let trackIdSeed = 0
let fxClipIdSeed = 0
let regularNoteIdSeed = 0
let tone: ToneNamespace | null = null
let animationFrameId: number | null = null
let backingStartTimeoutId: number | null = null
let players = new Map<number, import("tone").Player>()
let fxPlayers = new Map<number, import("tone").Player>()
let timelinePanPointerId: number | null = null
let timelinePanStartX = 0
let timelinePanStartY = 0
let timelinePanStartScrollLeft = 0
let timelinePanStartScrollTop = 0
let fxClipDrag:
  | {
      trackIndex: number
      clipId: number
      startClientX: number
      startMs: number
    }
  | null = null
let regularNoteDrag:
  | {
      trackIndex: number
      noteId: number
      startClientX: number
      startMs: number
      notes: Array<{
        trackIndex: number
        noteId: number
        startMs: number
      }>
    }
  | null = null

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
    (total, track) => total + (track.channelType === "regular" ? track.regularNotes.length : 0),
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
const sliderWhistleGuideSlots = computed(() =>
  [...markerSlots.value, ...sliderBodySlots.value].sort((left, right) => noteDisplayTime(left) - noteDisplayTime(right)),
)
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
const hasSelection = computed(() => selectedRegularNoteIds.value.size > 0)
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
const selectionStartTrackIndex = computed(() => {
  if (selectionAnchorTrackIndex.value === null || selectionFocusTrackIndex.value === null) {
    return 0
  }

  return Math.min(selectionAnchorTrackIndex.value, selectionFocusTrackIndex.value)
})
const selectionEndTrackIndex = computed(() => {
  if (selectionAnchorTrackIndex.value === null || selectionFocusTrackIndex.value === null) {
    return 0
  }

  return Math.max(selectionAnchorTrackIndex.value, selectionFocusTrackIndex.value)
})

const canPlay = computed(() => notes.value.length > 0)

function createTrack(name: string, noteCount: number): Track {
  trackIdSeed += 1
  const defaultSample = defaultSamples[(trackIdSeed - 1) % defaultSamples.length] ?? null

  return {
    id: trackIdSeed,
    channelType: "regular",
    collapsed: false,
    name,
    sampleName: defaultSample?.name ?? "No sample",
    sampleUrl: defaultSample?.url ?? null,
    sampleSource: defaultSample ? "default" : "none",
    customSampleBank: "normal",
    customSampleSound: "hitnormal",
    customSampleIndex: 1,
    customSample: null,
    regularNotes: [],
    fxClips: [],
    hits: Array(noteCount).fill(false),
  }
}

function createFxTrack(name: string): Track {
  trackIdSeed += 1

  return {
    id: trackIdSeed,
    channelType: "fx",
    collapsed: false,
    name,
    sampleName: "FX one-shots",
    sampleUrl: null,
    sampleSource: "none",
    customSampleBank: "normal",
    customSampleSound: "hitnormal",
    customSampleIndex: 1,
    customSample: null,
    regularNotes: [],
    fxClips: [],
    hits: Array(notes.value.length).fill(false),
  }
}

function createTrackForSample(sampleName: string, hits: boolean[]): Track {
  trackIdSeed += 1

  const defaultSample = defaultSamples.find((sample) => sample.name === sampleName)
  const parsedSample = parseSampleName(sampleName)

  return {
    id: trackIdSeed,
    channelType: "regular",
    collapsed: false,
    name: sampleName.replace(/\.wav$/i, ""),
    sampleName,
    sampleUrl: defaultSample?.url ?? null,
    sampleSource: defaultSample ? "default" : "none",
    customSampleBank: parsedSample?.bank ?? "normal",
    customSampleSound: parsedSample?.sound ?? "hitnormal",
    customSampleIndex: parsedSample?.sampleIndex ?? 1,
    customSample: null,
    regularNotes: createRegularNotesFromHits(hits),
    fxClips: [],
    hits,
  }
}

function createRegularNote(startMs: number, assignedNoteIndex: number | null): RegularNote {
  regularNoteIdSeed += 1

  return {
    id: regularNoteIdSeed,
    startMs,
    assignedNoteIndex,
  }
}

function createRegularNotesFromHits(hits: boolean[]) {
  return hits.flatMap((enabled, noteIndex) => {
    const note = notes.value[noteIndex]

    if (!enabled || !note) {
      return []
    }

    return [createRegularNote(noteDisplayTime(note), noteIndex)]
  })
}

function syncRegularTrackHits(track: Track) {
  track.hits = Array(notes.value.length).fill(false)

  if (track.channelType !== "regular") {
    return
  }

  for (const note of track.regularNotes) {
    const assignedNote = note.assignedNoteIndex !== null ? notes.value[note.assignedNoteIndex] : null

    if (assignedNote && canTrackAssignToNote(track, assignedNote)) {
      track.hits[note.assignedNoteIndex] = true
    }
  }
}

function captureUndoSnapshot() {
  undoStack.push({
    tracks: tracks.value.map((track) => ({
      trackId: track.id,
      regularNotes: track.regularNotes.map((note) => ({ ...note })),
      fxClips: track.fxClips.map((clip) => ({
        id: clip.id,
        bank: clip.bank,
        sound: clip.sound,
        startMs: clip.startMs,
        durationMs: clip.durationMs,
        assignedNoteIndex: clip.assignedNoteIndex,
      })),
    })),
    selectedRegularNoteIds: [...selectedRegularNoteIds.value],
    activeTrackIndex: activeTrackIndex.value,
  })

  if (undoStack.length > maxUndoSnapshots) {
    undoStack.shift()
  }
}

function undoLastEdit() {
  const snapshot = undoStack.pop()

  if (!snapshot) {
    clipboardStatus.value = "Nothing to undo."
    return
  }

  const snapshotsByTrack = new Map(snapshot.tracks.map((track) => [track.trackId, track]))

  for (const track of tracks.value) {
    const trackSnapshot = snapshotsByTrack.get(track.id)

    if (!trackSnapshot) {
      continue
    }

    if (track.channelType === "regular") {
      track.regularNotes = trackSnapshot.regularNotes.map((note) => ({ ...note }))
      syncRegularTrackHits(track)
    }

    if (track.channelType === "fx") {
      const clipSnapshotsById = new Map(trackSnapshot.fxClips.map((clip) => [clip.id, clip]))

      for (const clip of track.fxClips) {
        const clipSnapshot = clipSnapshotsById.get(clip.id)

        if (!clipSnapshot) {
          continue
        }

        clip.startMs = clipSnapshot.startMs
        clip.durationMs = clipSnapshot.durationMs
        clip.assignedNoteIndex = clipSnapshot.assignedNoteIndex
        clip.bank = clipSnapshot.bank
        clip.sound = clipSnapshot.sound
      }
    }
  }

  selectedRegularNoteIds.value = new Set(snapshot.selectedRegularNoteIds)
  activeTrackIndex.value = Math.min(snapshot.activeTrackIndex, Math.max(0, tracks.value.length - 1))
  clipboardStatus.value = "Undid last edit."
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
          regularNotes: track.channelType === "regular" ? [] : track.regularNotes,
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
    slots.push(createSlot(hitObject, hitObject.kind, hitObject.timeMs, hitObject.kind === "slider" ? 0 : undefined))

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

    const slideCount = Math.max(1, Math.round(hitObject.slides) || 1)
    const spanDurationMs = sliderDurationMs / slideCount

    slots.push(createSlot(hitObject, "slider-body", hitObject.timeMs + sliderDurationMs / 2))

    for (let edgeIndex = 1; edgeIndex <= slideCount; edgeIndex += 1) {
      const edgeKind = edgeIndex === slideCount ? "slider-end" : "slider-repeat"

      slots.push(createSlot(hitObject, edgeKind, hitObject.timeMs + spanDurationMs * edgeIndex, edgeIndex))
    }
  }

  return slots
}

function createSlot(
  hitObject: RawHitObject,
  kind: HitSlotKind,
  timeMs: number,
  edgeIndex?: number,
): OsuNote {
  return {
    id: `${hitObject.sourceIndex}-${kind}-${timeMs}`,
    index: 0,
    sourceIndex: hitObject.sourceIndex,
    edgeIndex,
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

    if (note.kind === "slider-end" || note.kind === "slider-repeat") {
      const edgeIndex = note.edgeIndex ?? hitObject.edgeSounds.length - 1
      const edgeSound = hitObject.edgeSounds[edgeIndex] ?? 0
      const edgeSet = hitObject.edgeSets[edgeIndex] ?? { normalSet: 0, additionSet: 0 }

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

function revokeFxClip(clip: FxClip) {
  URL.revokeObjectURL(clip.sampleUrl)
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
    for (const clip of track.fxClips) {
      revokeFxClip(clip)
    }
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
      channelType: track.channelType,
      collapsed: track.collapsed,
      name: track.name,
      sampleName: track.sampleName,
      sampleSource: track.sampleSource,
      customSampleBank: track.customSampleBank,
      customSampleSound: track.customSampleSound,
      customSampleIndex: track.customSampleIndex,
      customSample: serializeCustomSample(track.customSample),
      regularNotes: track.regularNotes.map((note) => ({ ...note })),
      fxClips: track.fxClips.map((clip) => ({
        id: clip.id,
        name: clip.name,
        bank: clip.bank,
        sound: clip.sound,
        mimeType: clip.mimeType,
        startMs: clip.startMs,
        durationMs: clip.durationMs,
        assignedNoteIndex: clip.assignedNoteIndex,
        dataUrl: arrayBufferToDataUrl(clip.data, clip.mimeType),
      })),
      hits: Array.from({ length: notes.value.length }, (_, noteIndex) =>
        track.regularNotes.some((note) => {
          const assignedNote = notes.value[noteIndex]

          return note.assignedNoteIndex === noteIndex && assignedNote && canTrackAssignToNote(track, assignedNote)
        }),
      ),
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
    const restoredHits = Array.from({ length: parsed.notes.length }, (_, index) =>
      Boolean(savedTrack.hits[index]),
    )
    const regularNotes = savedTrack.regularNotes
      ? savedTrack.regularNotes.map((note) => {
          regularNoteIdSeed = Math.max(regularNoteIdSeed, note.id)

          return { ...note }
        })
      : createRegularNotesFromHits(restoredHits)
    const fxClips: FxClip[] = []

    for (const savedClip of savedTrack.fxClips ?? []) {
      const data = await dataUrlToArrayBuffer(savedClip.dataUrl)
      fxClipIdSeed = Math.max(fxClipIdSeed, savedClip.id)
      fxClips.push({
        id: savedClip.id,
        name: savedClip.name,
        bank: savedClip.bank ?? "drum",
        sound: savedClip.sound ?? "hitfinish",
        sampleUrl: URL.createObjectURL(new Blob([data], { type: savedClip.mimeType })),
        mimeType: savedClip.mimeType,
        data,
        startMs: savedClip.startMs,
        durationMs: savedClip.durationMs,
        assignedNoteIndex: savedClip.assignedNoteIndex,
      })
    }

    const defaultSample = defaultSamples.find((sample) => sample.name === savedTrack.sampleName)
    const sampleUrl =
      savedTrack.sampleSource === "custom" && customSample
        ? URL.createObjectURL(new Blob([customSample.data], { type: customSample.mimeType }))
        : defaultSample?.url ?? null

    restoredTracks.push({
      id: trackIdSeed,
      channelType: savedTrack.channelType ?? "regular",
      collapsed: Boolean(savedTrack.collapsed),
      name: savedTrack.name,
      sampleName: savedTrack.sampleName,
      sampleUrl,
      sampleSource: savedTrack.sampleSource,
      customSampleBank: savedTrack.customSampleBank,
      customSampleSound: savedTrack.customSampleSound,
      customSampleIndex: savedTrack.customSampleIndex,
      customSample,
      regularNotes,
      fxClips,
      hits: restoredHits,
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

function selectDefaultHitsound(trackIndex: number, bank: SampleBank, sound: SampleSound) {
  const sample = defaultSamples.find((defaultSample) => defaultSample.name === getSampleFileName(bank, sound, 1))
  const track = tracks.value[trackIndex]

  if (!sample || !track) {
    return
  }

  hsPickerModes.value[track.id] = "default"
  selectDefaultSample(trackIndex, sample.url)
}

function selectCustomHitsoundType(trackIndex: number, bank: SampleBank, sound: SampleSound) {
  const track = tracks.value[trackIndex]

  if (!track) {
    return
  }

  track.customSampleBank = bank
  track.customSampleSound = sound
  hsPickerModes.value[track.id] = "custom"
  refreshCustomSampleNaming(track)
}

function getHitsoundPickerMode(track: Track): HitsoundPickerMode {
  return hsPickerModes.value[track.id] ?? (track.sampleSource === "custom" ? "custom" : "default")
}

function setHitsoundPickerMode(track: Track, mode: HitsoundPickerMode) {
  hsPickerModes.value[track.id] = mode
}

function isHitsoundPickerOpen(track: Track) {
  return hsPickerOpen.value[track.id] ?? false
}

function setHitsoundPickerOpen(event: Event, track: Track) {
  hsPickerOpen.value[track.id] = (event.currentTarget as HTMLDetailsElement).open
}

function isDefaultHitsoundSelected(track: Track, bank: SampleBank, sound: SampleSound) {
  return track.sampleSource === "default" && track.sampleName === getSampleFileName(bank, sound, 1)
}

function isCustomHitsoundTypeSelected(track: Track, bank: SampleBank, sound: SampleSound) {
  return track.customSampleBank === bank && track.customSampleSound === sound
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
  hsPickerModes.value[track.id] = "custom"
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

async function handleFxClipUpload(event: Event, trackIndex: number) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  const track = tracks.value[trackIndex]

  if (!file || !track || track.channelType !== "fx") {
    return
  }

  const sampleUrl = URL.createObjectURL(file)
  const data = await file.arrayBuffer()
  const clip: FxClip = {
    id: ++fxClipIdSeed,
    name: file.name,
    bank: "drum",
    sound: "hitfinish",
    sampleUrl,
    mimeType: file.type || "audio/wav",
    data,
    startMs: playbackAnchorMs.value,
    durationMs: 1_000,
    assignedNoteIndex: null,
  }

  track.fxClips.push(clip)
  selectedFxClipId.value = clip.id
  input.value = ""

  const audio = new Audio(sampleUrl)

  audio.addEventListener(
    "loadedmetadata",
    () => {
      if (Number.isFinite(audio.duration) && audio.duration > 0) {
        clip.durationMs = audio.duration * 1_000
      }
    },
    { once: true },
  )
}

function fxClipStyle(clip: FxClip) {
  const left = timeToPixel(clip.startMs)
  const width = Math.max(28, (clip.durationMs / 1_000) * pixelsPerSecond.value)

  return {
    left: `${left}px`,
    width: `${width}px`,
  }
}

function startFxClipDrag(event: PointerEvent, trackIndex: number, clip: FxClip) {
  if (event.button !== 0) {
    return
  }

  captureUndoSnapshot()
  fxClipDrag = {
    trackIndex,
    clipId: clip.id,
    startClientX: event.clientX,
    startMs: clip.startMs,
  }
  suppressNextTimelineClick.value = true
  event.preventDefault()
  event.stopPropagation()
}

function updateFxClipDrag(event: PointerEvent) {
  if (!fxClipDrag) {
    return
  }

  const track = tracks.value[fxClipDrag.trackIndex]
  const clip = track?.fxClips.find((candidate) => candidate.id === fxClipDrag?.clipId)

  if (!clip) {
    return
  }

  const deltaMs = ((event.clientX - fxClipDrag.startClientX) / pixelsPerSecond.value) * 1_000

  clip.startMs = Math.min(Math.max(timelineStartMs.value, fxClipDrag.startMs + deltaMs), durationMs.value)
  event.preventDefault()
}

function finishFxClipDrag() {
  fxClipDrag = null
}

function selectFxClip(trackIndex: number, clip: FxClip) {
  setActiveTrack(trackIndex)
  selectedFxClipId.value = clip.id
  assignFxClipToNearestSlot(clip)
}

function getSelectedFxClip(track: Track) {
  if (track.channelType !== "fx" || selectedFxClipId.value === null) {
    return null
  }

  return track.fxClips.find((clip) => clip.id === selectedFxClipId.value) ?? null
}

function updateSelectedFxClipBank(track: Track, event: Event) {
  const clip = getSelectedFxClip(track)
  const bank = (event.target as HTMLSelectElement).value as SampleBank

  if (!clip) {
    return
  }

  captureUndoSnapshot()
  clip.bank = bank
}

function updateSelectedFxClipSound(track: Track, event: Event) {
  const clip = getSelectedFxClip(track)
  const sound = (event.target as HTMLSelectElement).value as SampleSound

  if (!clip) {
    return
  }

  captureUndoSnapshot()
  clip.sound = sound
}

function assignFxClipToNearestSlot(clip: FxClip) {
  const nearestTime = findNearestNoteTime(clip.startMs)
  const noteIndex = findNoteIndexAtTime(nearestTime)

  if (noteIndex === -1) {
    return
  }

  captureUndoSnapshot()
  clip.startMs = nearestTime
  clip.assignedNoteIndex = noteIndex
}

function getRegularNoteKey(track: Track, note: RegularNote) {
  return `${track.id}:${note.id}`
}

function visibleRegularNotes(track: Track) {
  return track.regularNotes.filter(
    (note) => note.startMs >= visibleRangeStartMs.value && note.startMs <= visibleRangeEndMs.value,
  )
}

function regularNoteStyle(note: RegularNote) {
  const width = markerDiameter

  return {
    left: `${timeToPixel(note.startMs) - width / 2}px`,
    width: `${width}px`,
  }
}

function getTrackSampleSound(track: Track) {
  if (track.sampleSource === "custom" && track.customSample) {
    return track.customSample.sound
  }

  return parseSampleName(track.sampleName)?.sound ?? track.customSampleSound
}

function canTrackAssignToNote(track: Track, note: OsuNote) {
  return note.kind !== "slider-body" || getTrackSampleSound(track) === "sliderwhistle"
}

function getGuideCandidatesForTrack(track?: Track) {
  if (track?.channelType === "regular" && getTrackSampleSound(track) === "sliderwhistle") {
    return sliderWhistleGuideSlots.value
  }

  return markerSlots.value
}

function getNearestSortedGuideNote(timeMs: number, candidates: OsuNote[]) {
  if (!candidates.length) {
    return {
      nearestNote: null,
      nearestDistance: Number.POSITIVE_INFINITY,
    }
  }

  let low = 0
  let high = candidates.length - 1

  while (low < high) {
    const mid = Math.floor((low + high) / 2)

    if (noteDisplayTime(candidates[mid]) < timeMs) {
      low = mid + 1
    } else {
      high = mid
    }
  }

  const right = candidates[low]
  const left = candidates[Math.max(0, low - 1)]
  const rightDistance = right ? Math.abs(noteDisplayTime(right) - timeMs) : Number.POSITIVE_INFINITY
  const leftDistance = left ? Math.abs(noteDisplayTime(left) - timeMs) : Number.POSITIVE_INFINITY

  return leftDistance <= rightDistance
    ? { nearestNote: left, nearestDistance: leftDistance }
    : { nearestNote: right, nearestDistance: rightDistance }
}

function getNearestGuideNote(timeMs: number, track?: Track) {
  return getNearestSortedGuideNote(timeMs, getGuideCandidatesForTrack(track))
}

function snapRegularTime(timeMs: number, track?: Track, force = false) {
  const clampedTimeMs = Math.min(Math.max(timelineStartMs.value, timeMs), durationMs.value)
  const { nearestNote, nearestDistance } = getNearestGuideNote(clampedTimeMs, track)
  const thresholdMs = (guideSnapThresholdPx / pixelsPerSecond.value) * 1_000

  if (nearestNote && (force || nearestDistance <= thresholdMs)) {
    return {
      timeMs: noteDisplayTime(nearestNote),
      assignedNoteIndex: nearestNote.index,
    }
  }

  return {
    timeMs: clampedTimeMs,
    assignedNoteIndex: null,
  }
}

function getRegularAssignmentAtTime(timeMs: number, track: Track) {
  const { nearestNote, nearestDistance } = getNearestGuideNote(timeMs, track)
  const thresholdMs = (guideSnapThresholdPx / pixelsPerSecond.value) * 1_000

  return nearestNote && nearestDistance <= thresholdMs ? nearestNote.index : null
}

function getRegularNoteRefsForDrag(track: Track, trackIndex: number, note: RegularNote) {
  const noteKey = getRegularNoteKey(track, note)

  if (!selectedRegularNoteIds.value.has(noteKey)) {
    selectedRegularNoteIds.value = new Set([noteKey])

    return [{ trackIndex, noteId: note.id, startMs: note.startMs }]
  }

  return getSelectedRegularNoteRefs().map(({ trackIndex: selectedTrackIndex, note: selectedNote }) => ({
    trackIndex: selectedTrackIndex,
    noteId: selectedNote.id,
    startMs: selectedNote.startMs,
  }))
}

function addRegularNoteAtEvent(event: MouseEvent, trackIndex: number) {
  const target = event.target as HTMLElement | null
  const track = tracks.value[trackIndex]

  if (!track || track.channelType !== "regular" || track.collapsed) {
    return
  }

  if (target?.closest("button, input, select, label, audio, .lane-label, .placed-note")) {
    return
  }

  const snappedTime = snapRegularTime(getTimelineTimeFromClientX(event.clientX), track)

  captureUndoSnapshot()
  setActiveTrack(trackIndex)
  track.regularNotes.push(createRegularNote(snappedTime.timeMs, snappedTime.assignedNoteIndex))
  syncRegularTrackHits(track)
  suppressNextTimelineClick.value = true
  event.preventDefault()
}

function removeRegularNote(trackIndex: number, regularNoteId: number) {
  const track = tracks.value[trackIndex]

  if (!track || track.channelType !== "regular") {
    return
  }

  captureUndoSnapshot()
  track.regularNotes = track.regularNotes.filter((note) => note.id !== regularNoteId)
  syncRegularTrackHits(track)
  selectedRegularNoteIds.value.delete(`${track.id}:${regularNoteId}`)
  selectedRegularNoteIds.value = new Set(selectedRegularNoteIds.value)
}

function snapAllSounds() {
  let snappedCount = 0

  captureUndoSnapshot()

  for (const track of tracks.value) {
    if (track.channelType === "regular") {
      for (const note of track.regularNotes) {
        const snappedTime = snapRegularTime(note.startMs, track, true)

        note.startMs = snappedTime.timeMs
        note.assignedNoteIndex = snappedTime.assignedNoteIndex
        snappedCount += 1
      }

      syncRegularTrackHits(track)
      continue
    }

    for (const clip of track.fxClips) {
      const nearestTime = findNearestNoteTime(clip.startMs)
      const noteIndex = findNoteIndexAtTime(nearestTime)

      if (noteIndex === -1) {
        continue
      }

      clip.startMs = nearestTime
      clip.assignedNoteIndex = noteIndex
      snappedCount += 1
    }
  }

  clipboardStatus.value = `Snapped ${snappedCount} sounds to the nearest tick.`
}

function startRegularNoteDrag(event: PointerEvent, trackIndex: number, note: RegularNote) {
  if (event.button !== 0) {
    return
  }

  const track = tracks.value[trackIndex]

  if (!track || track.channelType !== "regular") {
    return
  }

  captureUndoSnapshot()
  regularNoteDrag = {
    trackIndex,
    noteId: note.id,
    startClientX: event.clientX,
    startMs: note.startMs,
    notes: getRegularNoteRefsForDrag(track, trackIndex, note),
  }
  suppressNextTimelineClick.value = true
  setActiveTrack(trackIndex)
  event.preventDefault()
  event.stopPropagation()
}

function updateRegularNoteDrag(event: PointerEvent) {
  if (!regularNoteDrag) {
    return
  }

  const track = tracks.value[regularNoteDrag.trackIndex]

  if (!track || track.channelType !== "regular") {
    return
  }

  const deltaMs = ((event.clientX - regularNoteDrag.startClientX) / pixelsPerSecond.value) * 1_000
  const anchorTarget = snapRegularTime(regularNoteDrag.startMs + deltaMs, track)
  const rawDragDeltaMs = anchorTarget.timeMs - regularNoteDrag.startMs
  const minStartMs = Math.min(...regularNoteDrag.notes.map((note) => note.startMs))
  const maxStartMs = Math.max(...regularNoteDrag.notes.map((note) => note.startMs))
  const clampedDragDeltaMs = Math.min(
    Math.max(rawDragDeltaMs, timelineStartMs.value - minStartMs),
    durationMs.value - maxStartMs,
  )
  const affectedTrackIndices = new Set<number>()

  for (const draggedNote of regularNoteDrag.notes) {
    const draggedTrack = tracks.value[draggedNote.trackIndex]

    if (!draggedTrack || draggedTrack.channelType !== "regular") {
      continue
    }

    const note = draggedTrack.regularNotes.find((candidate) => candidate.id === draggedNote.noteId)

    if (!note) {
      continue
    }

    note.startMs = draggedNote.startMs + clampedDragDeltaMs
    note.assignedNoteIndex = getRegularAssignmentAtTime(note.startMs, draggedTrack)
    affectedTrackIndices.add(draggedNote.trackIndex)
  }

  for (const trackIndex of affectedTrackIndices) {
    const affectedTrack = tracks.value[trackIndex]

    if (affectedTrack) {
      syncRegularTrackHits(affectedTrack)
    }
  }

  event.preventDefault()
}

function finishRegularNoteDrag() {
  regularNoteDrag = null
}

function removeFxClip(trackIndex: number, clipId: number) {
  const track = tracks.value[trackIndex]

  if (!track) {
    return
  }

  const clipIndex = track.fxClips.findIndex((clip) => clip.id === clipId)

  if (clipIndex === -1) {
    return
  }

  const [clip] = track.fxClips.splice(clipIndex, 1)

  if (clip) {
    if (selectedFxClipId.value === clip.id) {
      selectedFxClipId.value = null
    }

    revokeFxClip(clip)
    fxPlayers.get(clip.id)?.dispose()
    fxPlayers.delete(clip.id)
  }
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

function addRegularChannel() {
  tracks.value.push(createTrack(`HS ${tracks.value.length + 1}`, notes.value.length))
  activeTrackIndex.value = tracks.value.length - 1
}

function addFxChannel() {
  tracks.value.push(createFxTrack(`FX ${tracks.value.length + 1}`))
  activeTrackIndex.value = tracks.value.length - 1
}

function removeTrack(trackIndex: number) {
  const [track] = tracks.value.splice(trackIndex, 1)

  if (!track) {
    return
  }

  revokeCustomSample(track)
  for (const clip of track.fxClips) {
    if (selectedFxClipId.value === clip.id) {
      selectedFxClipId.value = null
    }

    revokeFxClip(clip)
    fxPlayers.get(clip.id)?.dispose()
    fxPlayers.delete(clip.id)
  }

  players.get(track.id)?.dispose()
  players.delete(track.id)
  delete hsPickerModes.value[track.id]
  delete hsPickerOpen.value[track.id]

  selectedRegularNoteIds.value = new Set(
    [...selectedRegularNoteIds.value].filter((noteKey) => !noteKey.startsWith(`${track.id}:`)),
  )

  if (activeTrackIndex.value > trackIndex) {
    activeTrackIndex.value -= 1
  } else if (activeTrackIndex.value >= tracks.value.length) {
    activeTrackIndex.value = Math.max(0, tracks.value.length - 1)
  }

  if (selectionTrackIndex.value === trackIndex) {
    selectionTrackIndex.value = null
    selectionAnchorMs.value = null
    selectionFocusMs.value = null
  } else if (selectionTrackIndex.value !== null && selectionTrackIndex.value > trackIndex) {
    selectionTrackIndex.value -= 1
  }

  if (selectionAnchorTrackIndex.value !== null && selectionAnchorTrackIndex.value > trackIndex) {
    selectionAnchorTrackIndex.value -= 1
  }

  if (selectionFocusTrackIndex.value !== null && selectionFocusTrackIndex.value > trackIndex) {
    selectionFocusTrackIndex.value -= 1
  }
}

function toggleTrackCollapsed(trackIndex: number) {
  const track = tracks.value[trackIndex]

  if (!track) {
    return
  }

  track.collapsed = !track.collapsed
}

function clearTrack(trackIndex: number) {
  const track = tracks.value[trackIndex]

  if (!track) {
    return
  }

  if (track.channelType === "fx") {
    captureUndoSnapshot()

    for (const clip of track.fxClips) {
      if (selectedFxClipId.value === clip.id) {
        selectedFxClipId.value = null
      }

      revokeFxClip(clip)
      fxPlayers.get(clip.id)?.dispose()
      fxPlayers.delete(clip.id)
    }

    track.fxClips = []
    return
  }

  captureUndoSnapshot()
  track.regularNotes = []
  track.hits = Array(notes.value.length).fill(false)
  selectedRegularNoteIds.value = new Set(
    [...selectedRegularNoteIds.value].filter((noteKey) => !noteKey.startsWith(`${track.id}:`)),
  )
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
  layer.additions = [...(layer.additions ?? []), sample]
  layer.addition = sample
}

function customIndexKey(bank: SampleBank, sound: SampleSound) {
  return `${bank}-${sound}`
}

function reserveCustomIndex(context: ExportContext, bank: SampleBank, sound: SampleSound, sampleIndex: number) {
  const key = customIndexKey(bank, sound)
  const occupied = context.occupiedCustomIndices.get(key) ?? new Set<number>()

  occupied.add(Math.max(1, Math.round(sampleIndex) || 1))
  context.occupiedCustomIndices.set(key, occupied)
}

function allocateCustomIndex(context: ExportContext, bank: SampleBank, sound: SampleSound) {
  const key = customIndexKey(bank, sound)
  const occupied = context.occupiedCustomIndices.get(key) ?? new Set<number>()
  let sampleIndex = 1

  while (occupied.has(sampleIndex)) {
    sampleIndex += 1
  }

  occupied.add(sampleIndex)
  context.occupiedCustomIndices.set(key, occupied)

  return sampleIndex
}

function addExportSampleToContext(context: ExportContext, sample: ExportSample) {
  if (!sample.data) {
    return
  }

  reserveCustomIndex(context, sample.bank, sample.sound, sample.sampleIndex)
  context.samplesByFileName.set(sample.fileName, sample)
}

function createFxExportSample(context: ExportContext, clip: FxClip, trackIndex: number) {
  const sampleIndex = allocateCustomIndex(context, clip.bank, clip.sound)
  const fileName = getSampleFileName(clip.bank, clip.sound, sampleIndex)
  const sample: ExportSample = {
    sampleName: fileName,
    bank: clip.bank,
    sound: clip.sound,
    sampleIndex,
    trackIndex: trackIndex + clip.id / 1_000_000,
    fileName,
    data: clip.data,
  }

  context.fxSamplesByClipId.set(clip.id, sample)
  context.samplesByFileName.set(fileName, sample)

  return sample
}

function createExportContext(): ExportContext {
  const context: ExportContext = {
    samplesByFileName: new Map(),
    fxSamplesByClipId: new Map(),
    occupiedCustomIndices: new Map(),
    mixedSamplesByKey: new Map(),
  }

  if (notes.value.length) {
    addExportSampleToContext(context, getFallbackExportSample())
  }

  tracks.value.forEach((track, trackIndex) => {
    if (track.channelType === "regular") {
      const hasAssignedNotes = track.regularNotes.some((regularNote) => regularNote.assignedNoteIndex !== null)
      const sample = hasAssignedNotes ? getExportSampleForTrack(track, trackIndex) : null

      if (sample) {
        addExportSampleToContext(context, sample)
      }

      return
    }

    for (const clip of track.fxClips) {
      if (clip.assignedNoteIndex !== null) {
        createFxExportSample(context, clip, trackIndex)
      }
    }
  })

  return context
}

function canSampleAssignToNote(sample: ExportSample, note: OsuNote) {
  return note.kind !== "slider-body" || sample.sound === "sliderwhistle"
}

function getSelectedHitsoundLayer(noteIndex: number, fallbackNormal: ExportSample, context: ExportContext) {
  const layer: HitsoundLayer = {
    hitSoundBits: 0,
  }
  let hasSelectedSample = false

  // TODO: Resolve true hitsound conflicts explicitly in the UI. For now, the
  // highest-numbered track wins within each osu field. This means hitnormal
  // picks the highest normal layer, and additions share the highest addition
  // set/index while OR-ing together their clap/finish/whistle bits.
  tracks.value.forEach((track, trackIndex) => {
    if (
      track.channelType !== "regular" ||
      !track.regularNotes.some((regularNote) => {
        const assignedNote = notes.value[noteIndex]

        return (
          regularNote.assignedNoteIndex === noteIndex &&
          assignedNote &&
          canTrackAssignToNote(track, assignedNote)
        )
      })
    ) {
      return
    }

    const exportSample = getExportSampleForTrack(track, trackIndex)

    if (exportSample) {
      hasSelectedSample = true
      mergeSampleIntoLayer(layer, exportSample)
    }
  })

  tracks.value.forEach((track) => {
    if (track.channelType !== "fx") {
      return
    }

    for (const clip of track.fxClips) {
      if (clip.assignedNoteIndex !== noteIndex) {
        continue
      }

      const assignedNote = notes.value[noteIndex]
      const exportSample = context.fxSamplesByClipId.get(clip.id)

      if (assignedNote && exportSample && canSampleAssignToNote(exportSample, assignedNote)) {
        hasSelectedSample = true
        mergeSampleIntoLayer(layer, exportSample)
      }
    }
  })

  if (!layer.normal) {
    layer.normal = fallbackNormal
  }

  return hasSelectedSample ? layer : null
}

async function buildSourceHitsoundAssignments(context: ExportContext) {
  const assignments = new Map<number, SourceHitsoundAssignment>()
  const fallbackSample = getFallbackExportSample()
  const sourceSlots = new Map<number, { hasHead: boolean, edgeIndices: Set<number> }>()

  for (const note of notes.value) {
    const slots = sourceSlots.get(note.sourceIndex) ?? { hasHead: false, edgeIndices: new Set<number>() }

    if (note.kind === "slider-end" || note.kind === "slider-repeat") {
      if (note.edgeIndex !== undefined) {
        slots.edgeIndices.add(note.edgeIndex)
      }
    } else if (note.kind !== "slider-body") {
      slots.hasHead = true
    }

    sourceSlots.set(note.sourceIndex, slots)

    const hitsoundLayer = getSelectedHitsoundLayer(note.index, fallbackSample, context)

    if (!hitsoundLayer) {
      continue
    }

    const resolvedHitsoundLayer = await resolveHitsoundLayer(hitsoundLayer, context)
    const assignment = assignments.get(note.sourceIndex) ?? {}

    if (note.kind === "slider-end" || note.kind === "slider-repeat") {
      if (note.edgeIndex !== undefined) {
        assignment.sliderEdges = assignment.sliderEdges ?? new Map<number, HitsoundLayer>()
        assignment.sliderEdges.set(note.edgeIndex, resolvedHitsoundLayer)
      }
    } else if (note.kind === "slider-body") {
      assignment.sliderBody = resolvedHitsoundLayer
    } else {
      assignment.head = resolvedHitsoundLayer
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

    for (const edgeIndex of slots.edgeIndices) {
      assignment.sliderEdges = assignment.sliderEdges ?? new Map<number, HitsoundLayer>()

      if (!assignment.sliderEdges.has(edgeIndex)) {
        assignment.sliderEdges.set(edgeIndex, {
          normal: fallbackSample,
          hitSoundBits: 0,
        })
      }
    }

    assignments.set(sourceIndex, assignment)
  }

  for (const assignment of assignments.values()) {
    const sliderBodyWhistle =
      assignment.sliderBody?.addition?.sound === "sliderwhistle" ? assignment.sliderBody : undefined

    if (sliderBodyWhistle) {
      assignment.head = await mergeResolvedLayers(assignment.head, sliderBodyWhistle, context)
      assignment.sliderBody = undefined
    }
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

function getAdditionPriority(sound: SampleSound) {
  const priorities: Record<SampleSound, number> = {
    hitnormal: 0,
    hitwhistle: 2,
    sliderwhistle: 2,
    hitclap: 3,
    hitfinish: 4,
  }

  return priorities[sound]
}

function chooseRepresentativeAddition(additions: ExportSample[]) {
  return additions.reduce((best, sample) => {
    const priorityDelta = getAdditionPriority(sample.sound) - getAdditionPriority(best.sound)

    if (priorityDelta > 0) {
      return sample
    }

    if (priorityDelta === 0 && sample.trackIndex > best.trackIndex) {
      return sample
    }

    return best
  })
}

function canRepresentAdditionsDirectly(additions: ExportSample[]) {
  if (additions.length <= 1) {
    return true
  }

  const [first] = additions

  return additions.every(
    (sample) => sample.bank === first.bank && sample.sampleIndex === first.sampleIndex,
  )
}

async function getExportSampleAudioData(sample: ExportSample) {
  if (sample.data) {
    return sample.data.slice(0)
  }

  const defaultSample = defaultSamples.find((candidate) => candidate.name === sample.fileName)

  if (!defaultSample) {
    throw new Error(`Could not find audio data for ${sample.fileName}`)
  }

  const response = await fetch(defaultSample.url)

  if (!response.ok) {
    throw new Error(`Could not load ${sample.fileName}`)
  }

  return response.arrayBuffer()
}

function writeAscii(view: DataView, offset: number, value: string) {
  for (let index = 0; index < value.length; index += 1) {
    view.setUint8(offset + index, value.charCodeAt(index))
  }
}

function audioBufferToWav(buffer: AudioBuffer) {
  const channelCount = buffer.numberOfChannels
  const bytesPerSample = 2
  const blockAlign = channelCount * bytesPerSample
  const dataByteLength = buffer.length * blockAlign
  const arrayBuffer = new ArrayBuffer(44 + dataByteLength)
  const view = new DataView(arrayBuffer)
  let offset = 0

  writeAscii(view, offset, "RIFF")
  offset += 4
  view.setUint32(offset, 36 + dataByteLength, true)
  offset += 4
  writeAscii(view, offset, "WAVE")
  offset += 4
  writeAscii(view, offset, "fmt ")
  offset += 4
  view.setUint32(offset, 16, true)
  offset += 4
  view.setUint16(offset, 1, true)
  offset += 2
  view.setUint16(offset, channelCount, true)
  offset += 2
  view.setUint32(offset, buffer.sampleRate, true)
  offset += 4
  view.setUint32(offset, buffer.sampleRate * blockAlign, true)
  offset += 4
  view.setUint16(offset, blockAlign, true)
  offset += 2
  view.setUint16(offset, bytesPerSample * 8, true)
  offset += 2
  writeAscii(view, offset, "data")
  offset += 4
  view.setUint32(offset, dataByteLength, true)
  offset += 4

  const channelData = Array.from({ length: channelCount }, (_, channelIndex) =>
    buffer.getChannelData(channelIndex),
  )

  for (let sampleIndex = 0; sampleIndex < buffer.length; sampleIndex += 1) {
    for (let channelIndex = 0; channelIndex < channelCount; channelIndex += 1) {
      const sample = Math.max(-1, Math.min(1, channelData[channelIndex][sampleIndex] ?? 0))
      const pcm = sample < 0 ? sample * 0x8000 : sample * 0x7fff

      view.setInt16(offset, pcm, true)
      offset += 2
    }
  }

  return arrayBuffer
}

async function mixExportSamples(samples: ExportSample[]) {
  const AudioContextClass =
    window.AudioContext ?? (window as Window & typeof globalThis & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext

  if (!AudioContextClass) {
    throw new Error("This browser cannot decode audio for FX sample export.")
  }

  const audioContext = new AudioContextClass()

  try {
    const decodedBuffers = await Promise.all(
      samples.map(async (sample) => audioContext.decodeAudioData(await getExportSampleAudioData(sample))),
    )
    const sampleRate = Math.max(44_100, ...decodedBuffers.map((buffer) => buffer.sampleRate))
    const channelCount = Math.max(1, ...decodedBuffers.map((buffer) => buffer.numberOfChannels))
    const frameLength = Math.max(
      1,
      ...decodedBuffers.map((buffer) => Math.ceil(buffer.duration * sampleRate)),
    )
    const offlineContext = new OfflineAudioContext(channelCount, frameLength, sampleRate)

    for (const buffer of decodedBuffers) {
      const source = offlineContext.createBufferSource()

      source.buffer = buffer
      source.connect(offlineContext.destination)
      source.start(0)
    }

    return audioBufferToWav(await offlineContext.startRendering())
  } finally {
    await audioContext.close()
  }
}

function getMixedAdditionKey(additions: ExportSample[], representative: ExportSample) {
  return [
    representative.bank,
    representative.sound,
    ...additions
      .map((sample) => `${sample.fileName}:${sample.trackIndex}`)
      .sort(),
  ].join("|")
}

async function createMixedAdditionSample(context: ExportContext, additions: ExportSample[]) {
  const representative = chooseRepresentativeAddition(additions)
  const key = getMixedAdditionKey(additions, representative)
  const cachedSample = context.mixedSamplesByKey.get(key)

  if (cachedSample) {
    return cachedSample
  }

  const sampleIndex = allocateCustomIndex(context, representative.bank, representative.sound)
  const fileName = getSampleFileName(representative.bank, representative.sound, sampleIndex)
  const mixedSample: ExportSample = {
    sampleName: fileName,
    bank: representative.bank,
    sound: representative.sound,
    sampleIndex,
    trackIndex: representative.trackIndex,
    fileName,
    data: await mixExportSamples(additions),
  }

  context.mixedSamplesByKey.set(key, mixedSample)
  context.samplesByFileName.set(fileName, mixedSample)

  return mixedSample
}

async function resolveHitsoundLayer(layer: HitsoundLayer, context: ExportContext) {
  const additions = layer.additions ?? (layer.addition ? [layer.addition] : [])

  if (!additions.length) {
    return {
      normal: layer.normal,
      hitSoundBits: 0,
    }
  }

  if (canRepresentAdditionsDirectly(additions)) {
    return {
      normal: layer.normal,
      addition: chooseRepresentativeAddition(additions),
      additions,
      hitSoundBits: additions.reduce((bits, sample) => bits | getHitSoundBit(sample.sound), 0),
    }
  }

  const mixedSample = await createMixedAdditionSample(context, additions)

  return {
    normal: layer.normal,
    addition: mixedSample,
    additions: [mixedSample],
    hitSoundBits: getHitSoundBit(mixedSample.sound),
  }
}

function getLayerAdditions(layer: HitsoundLayer | undefined) {
  return layer?.additions ?? (layer?.addition ? [layer.addition] : [])
}

async function mergeResolvedLayers(
  left: HitsoundLayer | undefined,
  right: HitsoundLayer | undefined,
  context: ExportContext,
) {
  if (!left) {
    return right
  }

  if (!right) {
    return left
  }

  const normal =
    right.normal && (!left.normal || right.normal.trackIndex > left.normal.trackIndex)
      ? right.normal
      : left.normal

  return resolveHitsoundLayer(
    {
      normal,
      additions: [...getLayerAdditions(left), ...getLayerAdditions(right)],
      hitSoundBits: left.hitSoundBits | right.hitSoundBits,
    },
    context,
  )
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
  edgeIndex: number,
) {
  const { edgeSounds, edgeSets } = normalizeSliderEdgeParts(parts)
  const clampedEdgeIndex = Math.min(Math.max(0, edgeIndex), edgeSounds.length - 1)

  edgeSounds[clampedEdgeIndex] = String(layer.hitSoundBits)
  edgeSets[clampedEdgeIndex] = formatEdgeSet(layer)
  parts[8] = edgeSounds.join("|")
  parts[9] = edgeSets.join("|")
  parts[10] = applyLayerToHitSample(parts[10], layer)
}

function rewriteHitObjectLine(line: string, assignment: SourceHitsoundAssignment) {
  const parts = line.split(",")
  const kind = getObjectKind(Number(parts[3]))

  if (kind === "slider") {
    const sliderHeadLayer = assignment.head

    if (sliderHeadLayer) {
      applyHeadHitsound(parts, kind, sliderHeadLayer)
      applySliderEdgeHitsound(parts, sliderHeadLayer, 0)
    }

    for (const [edgeIndex, edgeLayer] of assignment.sliderEdges ?? []) {
      applySliderEdgeHitsound(parts, edgeLayer, edgeIndex)
    }
  } else if (assignment.head) {
    applyHeadHitsound(parts, kind, assignment.head)
  }

  return parts.join(",")
}

async function buildHitsoundedOsuText(context: ExportContext) {
  if (!originalOsuText.value || !hitObjectLineIndices.value.length) {
    return ""
  }

  const lines = originalOsuText.value.split(/\r?\n/)
  const assignments = await buildSourceHitsoundAssignments(context)

  for (const [sourceIndex, assignment] of assignments.entries()) {
    const lineIndex = hitObjectLineIndices.value[sourceIndex]

    if (lineIndex === undefined || !lines[lineIndex]) {
      continue
    }

    lines[lineIndex] = rewriteHitObjectLine(lines[lineIndex], assignment)
  }

  return lines.join("\n")
}

function getUsedExportSamples(context: ExportContext) {
  return [...context.samplesByFileName.values()]
}

async function addSampleToZip(zip: InstanceType<typeof import("jszip").default>, sample: ExportSample) {
  if (sample.data) {
    zip.file(sample.fileName, sample.data)
  }
}

async function downloadHitsoundedOsu() {
  const exportContext = createExportContext()
  const hitsoundedOsuText = await buildHitsoundedOsuText(exportContext)

  if (!hitsoundedOsuText) {
    return
  }

  const { default: JSZip } = await import("jszip")
  const zip = new JSZip()
  const baseName = originalOsuFileName.value.replace(/\.osu$/i, "") || "beatmap"

  zip.file(`${baseName} [hitsounded].osu`, hitsoundedOsuText)

  for (const sample of getUsedExportSamples(exportContext)) {
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
  const nearestNote = getNearestSortedGuideNote(timeMs, markerSlots.value).nearestNote

  return nearestNote ? noteDisplayTime(nearestNote) : timeMs
}

function findNoteIndexAtTime(timeMs: number) {
  const { nearestNote, nearestDistance } = getNearestSortedGuideNote(timeMs, markerSlots.value)
  const toleranceMs = 3

  return nearestNote && nearestDistance <= toleranceMs ? nearestNote.index : -1
}

function selectionMarqueeStyle() {
  const startX = timeToPixel(selectionStartMs.value)
  const endX = timeToPixel(selectionEndMs.value)
  const startTop = getTrackTop(selectionStartTrackIndex.value)
  const endBottom = getTrackTop(selectionEndTrackIndex.value) + getTrackLaneHeight(selectionEndTrackIndex.value)

  return {
    left: `${startX}px`,
    width: `${Math.max(1, endX - startX)}px`,
    top: `${timelineHeaderHeight + startTop}px`,
    height: `${Math.max(1, endBottom - startTop)}px`,
  }
}

function getTrackLaneHeight(trackIndex: number) {
  const track = tracks.value[trackIndex]

  if (!track) {
    return closedTrackLaneHeight
  }

  if (track.collapsed) {
    return collapsedTrackLaneHeight
  }

  if (track.channelType === "fx") {
    return getSelectedFxClip(track) ? fxEditorTrackLaneHeight : fxTrackLaneHeight
  }

  if (!isHitsoundPickerOpen(track)) {
    return closedTrackLaneHeight
  }

  return getHitsoundPickerMode(track) === "custom" ? customPickerTrackLaneHeight : defaultPickerTrackLaneHeight
}

function getTrackTop(trackIndex: number) {
  let top = 0

  for (let index = 0; index < trackIndex; index += 1) {
    top += getTrackLaneHeight(index)
  }

  return top
}

function getTrackIndexFromClientY(clientY: number) {
  const scroller = timelineScroll.value

  if (!scroller) {
    return activeTrackIndex.value
  }

  const rect = scroller.getBoundingClientRect()
  const yInContent = clientY - rect.top + scroller.scrollTop - timelineHeaderHeight
  let accumulatedTop = 0

  for (const [trackIndex] of tracks.value.entries()) {
    accumulatedTop += getTrackLaneHeight(trackIndex)

    if (yInContent < accumulatedTop) {
      return trackIndex
    }
  }

  return Math.max(0, tracks.value.length - 1)
}

function getSelectedRegularNoteRefs() {
  const selectedIds = selectedRegularNoteIds.value
  const refs: Array<{ track: Track, trackIndex: number, note: RegularNote }> = []

  tracks.value.forEach((track, trackIndex) => {
    if (track.channelType !== "regular") {
      return
    }

    for (const note of track.regularNotes) {
      if (selectedIds.has(getRegularNoteKey(track, note))) {
        refs.push({ track, trackIndex, note })
      }
    }
  })

  return refs
}

function setSelectedRegularNotesFromMarquee() {
  const nextSelection = new Set<string>()

  for (let trackIndex = selectionStartTrackIndex.value; trackIndex <= selectionEndTrackIndex.value; trackIndex += 1) {
    const track = tracks.value[trackIndex]

    if (!track || track.channelType !== "regular") {
      continue
    }

    for (const note of track.regularNotes) {
      if (note.startMs >= selectionStartMs.value && note.startMs <= selectionEndMs.value) {
        nextSelection.add(getRegularNoteKey(track, note))
      }
    }
  }

  selectedRegularNoteIds.value = nextSelection
}

function startRangeSelection(event: PointerEvent, trackIndex: number) {
  const target = event.target as HTMLElement | null
  const track = tracks.value[trackIndex]

  if (event.button !== 0) {
    return
  }

  if (!track || track.channelType === "fx" || track.collapsed) {
    return
  }

  if (target?.closest("button, input, select, label, audio, .lane-label, .placed-note")) {
    return
  }

  setActiveTrack(trackIndex)
  selectedRegularNoteIds.value = new Set()
  selectionTrackIndex.value = trackIndex
  selectionAnchorMs.value = getTimelineTimeFromClientX(event.clientX)
  selectionFocusMs.value = selectionAnchorMs.value
  selectionAnchorTrackIndex.value = trackIndex
  selectionFocusTrackIndex.value = trackIndex
  isSelectingRange.value = true
  suppressNextTimelineClick.value = true
  event.preventDefault()
}

function updateRangeSelection(event: PointerEvent) {
  if (!isSelectingRange.value) {
    return
  }

  selectionFocusMs.value = getTimelineTimeFromClientX(event.clientX)
  selectionFocusTrackIndex.value = getTrackIndexFromClientY(event.clientY)
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
    selectionAnchorTrackIndex.value = null
    selectionFocusTrackIndex.value = null
    suppressNextTimelineClick.value = false
    clipboardStatus.value = ""
    return
  }

  setSelectedRegularNotesFromMarquee()
  selectionTrackIndex.value = null
  selectionAnchorMs.value = null
  selectionFocusMs.value = null
  selectionAnchorTrackIndex.value = null
  selectionFocusTrackIndex.value = null
  clipboardStatus.value = selectedRegularNoteIds.value.size
    ? `Selected ${selectedRegularNoteIds.value.size} notes.`
    : "No notes selected."
}

function clearSelection() {
  selectedRegularNoteIds.value = new Set()
  selectionTrackIndex.value = null
  selectionAnchorMs.value = null
  selectionFocusMs.value = null
  selectionAnchorTrackIndex.value = null
  selectionFocusTrackIndex.value = null
  isSelectingRange.value = false
  suppressNextTimelineClick.value = false
  clipboardStatus.value = "Selection cleared."
}

function copySelection() {
  const selectedNotes = getSelectedRegularNoteRefs()

  if (!selectedNotes.length) {
    clipboardStatus.value = "Drag a marquee around notes to select a pattern first."
    return
  }

  const firstTimeMs = Math.min(...selectedNotes.map(({ note }) => note.startMs))
  const lastTimeMs = Math.max(...selectedNotes.map(({ note }) => note.startMs))
  const firstTrackIndex = Math.min(...selectedNotes.map(({ trackIndex }) => trackIndex))
  const selectedTrackCount = new Set(selectedNotes.map(({ trackIndex }) => trackIndex)).size

  copiedPattern.value = {
    sourceTrackName: `${selectedTrackCount} channel${selectedTrackCount === 1 ? "" : "s"}`,
    durationMs: Math.max(0, lastTimeMs - firstTimeMs),
    hits: selectedNotes.map(({ trackIndex, note }) => ({
      offsetMs: note.startMs - firstTimeMs,
      trackOffset: trackIndex - firstTrackIndex,
    })),
  }
  clipboardStatus.value = `Copied ${copiedPattern.value.hits.length} notes from ${copiedPattern.value.sourceTrackName}.`
}

function pasteSelection() {
  const pattern = copiedPattern.value

  if (!pattern) {
    clipboardStatus.value = "Copy a selected pattern before pasting."
    return
  }

  captureUndoSnapshot()
  const activeTrack = tracks.value[activeTrackIndex.value]
  const pasteStart = snapRegularTime(
    currentTimeMs.value,
    activeTrack?.channelType === "regular" ? activeTrack : undefined,
  )
  const pasteStartMs = pasteStart.timeMs
  const pasteEndMs = pasteStartMs + pattern.durationMs
  const targetTrackIndices = new Set(
    pattern.hits
      .map((copiedHit) => activeTrackIndex.value + copiedHit.trackOffset)
      .filter((trackIndex) => tracks.value[trackIndex]?.channelType === "regular"),
  )

  for (const trackIndex of targetTrackIndices) {
    const track = tracks.value[trackIndex]

    if (!track) {
      continue
    }

    track.regularNotes = track.regularNotes.filter((note) => note.startMs < pasteStartMs || note.startMs > pasteEndMs)
  }

  let pastedCount = 0

  for (const copiedHit of pattern.hits) {
    const targetTrack = tracks.value[activeTrackIndex.value + copiedHit.trackOffset]

    if (!targetTrack || targetTrack.channelType !== "regular") {
      continue
    }

    const snappedTime = snapRegularTime(pasteStartMs + copiedHit.offsetMs, targetTrack)

    targetTrack.regularNotes.push(createRegularNote(snappedTime.timeMs, snappedTime.assignedNoteIndex))
    pastedCount += 1
  }

  for (const trackIndex of targetTrackIndices) {
    const track = tracks.value[trackIndex]

    if (track) {
      syncRegularTrackHits(track)
    }
  }

  clearSelection()
  clipboardStatus.value = `Pasted ${pastedCount} notes starting at ${formatTime(pasteStartMs)}.`
}

function clearSelectedRegion() {
  const selectedIds = selectedRegularNoteIds.value

  if (!selectedIds.size) {
    clipboardStatus.value = "Drag a marquee around notes first."
    return
  }

  captureUndoSnapshot()
  let clearedCount = 0

  for (const track of tracks.value) {
    if (track.channelType !== "regular") {
      continue
    }

    const beforeCount = track.regularNotes.length

    track.regularNotes = track.regularNotes.filter((note) => !selectedIds.has(getRegularNoteKey(track, note)))
    clearedCount += beforeCount - track.regularNotes.length
    syncRegularTrackHits(track)
  }

  clearSelection()
  clipboardStatus.value = `Cleared ${clearedCount} selected notes.`
}

function selectAllNotesInAllTracks() {
  if (!tracks.value.length || !notes.value.length) {
    clipboardStatus.value = "Load a map first."
    return
  }

  const nextSelection = new Set<string>()

  for (const track of tracks.value) {
    if (track.channelType !== "regular") {
      continue
    }

    for (const note of track.regularNotes) {
      nextSelection.add(getRegularNoteKey(track, note))
    }
  }

  selectedRegularNoteIds.value = nextSelection
  clipboardStatus.value = `Selected ${nextSelection.size} notes across regular channels.`
}

function selectAllNotesInActiveTrack() {
  const track = tracks.value[activeTrackIndex.value]

  if (!track || track.channelType !== "regular") {
    clipboardStatus.value = "Select a regular channel first."
    return
  }

  selectedRegularNoteIds.value = new Set(track.regularNotes.map((note) => getRegularNoteKey(track, note)))
  clipboardStatus.value = `Selected ${track.regularNotes.length} notes in ${track.name}.`
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

  if ((event.ctrlKey || event.metaKey) && key === "z") {
    event.preventDefault()
    undoLastEdit()
    return
  }

  if ((event.ctrlKey || event.metaKey) && key === "a") {
    event.preventDefault()
    selectAllNotesInAllTracks()
    return
  }

  if ((event.ctrlKey || event.metaKey) && key === "k") {
    event.preventDefault()
    selectAllNotesInActiveTrack()
    return
  }

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
    if (track.channelType === "fx") {
      for (const clip of track.fxClips) {
        const player = fxPlayers.get(clip.id)

        if (!player || clip.startMs < startTimeMs - 1) {
          continue
        }

        transport.scheduleOnce((time) => {
          player.start(time)
        }, Math.max(0, clip.startMs / 1_000))
      }

      continue
    }

    const player = players.get(track.id)

    if (!player) {
      continue
    }

    for (const regularNote of track.regularNotes) {
      const scheduledTimeMs = regularNote.startMs

      if (scheduledTimeMs < startTimeMs - 1) {
        continue
      }

      const scheduledSeconds = Math.max(0, (scheduledTimeMs + audioOffsetMs.value) / 1_000)

      transport.scheduleOnce((time) => {
        player.start(time)
      }, scheduledSeconds)
    }
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

    for (const player of fxPlayers.values()) {
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

  for (const player of fxPlayers.values()) {
    player.dispose()
  }

  players = new Map()
  fxPlayers = new Map()

  for (const track of tracks.value) {
    if (track.channelType === "regular" && track.sampleUrl) {
      players.set(track.id, new toneApi.Player(track.sampleUrl).toDestination())
      continue
    }

    if (track.channelType === "fx") {
      for (const clip of track.fxClips) {
        fxPlayers.set(clip.id, new toneApi.Player(clip.sampleUrl).toDestination())
      }
    }
  }

  if (players.size > 0 || fxPlayers.size > 0) {
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
  updateFxClipDrag(event)
  updateRegularNoteDrag(event)
  updateTimelinePan(event)
  updateRangeSelection(event)
}

function handleTimelinePointerUp(event: PointerEvent) {
  finishFxClipDrag()
  finishRegularNoteDrag()
  finishTimelinePan(event)
  finishRangeSelection()
}

function handleTimelinePointerLeave(event: PointerEvent) {
  finishFxClipDrag()
  finishRegularNoteDrag()

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
    "--track-lane-height": `${getTrackLaneHeight(trackIndex)}px`,
  }
}

function channelTypeLabel(track: Track) {
  return track.channelType === "fx" ? "FX" : "HS"
}

function trackHitCount(track: Track) {
  if (track.channelType === "fx") {
    return track.fxClips.length
  }

  return track.regularNotes.length
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
    "slider-repeat": "slider repeat",
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

  for (const player of fxPlayers.values()) {
    player.dispose()
  }

  for (const track of tracks.value) {
    revokeCustomSample(track)
    for (const clip of track.fxClips) {
      revokeFxClip(clip)
    }
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

        <div class="channel-add-controls">
          <button class="ghost-button" type="button" @click="addRegularChannel">Add HS</button>
          <button class="ghost-button" type="button" @click="addFxChannel">Add FX</button>
          <button class="ghost-button" type="button" @click="snapAllSounds">Snap all</button>
        </div>

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

          <div class="rhythm-preview-lane" aria-hidden="true">
            <span class="ruler-label preview-label">Rhythm</span>
            <span
              v-for="note in visibleSliderBodySlots"
              :key="`preview-body-${note.id}`"
              class="preview-slider-body"
              :style="sliderBodyStyle(note)"
            />
            <span
              v-for="note in visibleMarkerSlots"
              :key="`preview-${note.id}`"
              class="preview-note"
              :style="{ left: noteLeft(note) }"
            />
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
            v-if="isSelectingRange && selectionAnchorMs !== null && selectionFocusMs !== null"
            class="selection-marquee"
            :style="selectionMarqueeStyle()"
          />

          <div
            v-for="(track, trackIndex) in tracks"
            :key="track.id"
            class="track-lane"
            :class="{
              active: trackIndex === activeTrackIndex,
              collapsed: track.collapsed,
              'fx-lane': track.channelType === 'fx',
            }"
            :style="trackLaneStyle(trackIndex)"
            @dblclick="addRegularNoteAtEvent($event, trackIndex)"
            @pointerdown="startRangeSelection($event, trackIndex)"
          >
            <div class="lane-label" @click.stop="setActiveTrack(trackIndex)">
              <div class="lane-header">
                <input v-model="track.name" class="lane-name-input" aria-label="Channel name" />
                <span v-if="!track.collapsed">{{ channelTypeLabel(track) }}</span>
                <button
                  class="lane-icon-button"
                  type="button"
                  :aria-label="track.collapsed ? 'Expand channel' : 'Collapse channel'"
                  @click.stop="toggleTrackCollapsed(trackIndex)"
                >
                  {{ track.collapsed ? "+" : "-" }}
                </button>
                <button
                  v-if="!track.collapsed"
                  class="lane-icon-button"
                  type="button"
                  aria-label="Remove channel"
                  @click.stop="removeTrack(trackIndex)"
                >
                  x
                </button>
                <button
                  v-if="!track.collapsed"
                  class="lane-pill-button"
                  type="button"
                  @click.stop="clearTrack(trackIndex)"
                >
                  Clear
                </button>
              </div>

              <template v-if="track.channelType === 'regular' && !track.collapsed">
                <details class="hs-picker" @toggle="setHitsoundPickerOpen($event, track)">
                  <summary>
                    <span>HS</span>
                    <strong>{{ track.sampleName }}</strong>
                  </summary>

                  <div class="hs-source-toggle" role="group" aria-label="Hitsound source">
                    <span class="hs-source-label">Source</span>
                    <button
                      type="button"
                      :aria-pressed="getHitsoundPickerMode(track) === 'default'"
                      :class="{ selected: getHitsoundPickerMode(track) === 'default' }"
                      @click.stop="setHitsoundPickerMode(track, 'default')"
                    >
                      Default
                    </button>
                    <button
                      type="button"
                      :aria-pressed="getHitsoundPickerMode(track) === 'custom'"
                      :class="{ selected: getHitsoundPickerMode(track) === 'custom' }"
                      @click.stop="setHitsoundPickerMode(track, 'custom')"
                    >
                      Custom
                    </button>
                  </div>

                  <div v-if="getHitsoundPickerMode(track) === 'default'" class="hs-picker-section">
                    <span class="hs-picker-root">default</span>
                    <div class="hs-bank-grid">
                      <div v-for="bank in sampleBanks" :key="`default-${bank}`" class="hs-bank-group">
                        <span>{{ bank }}</span>
                        <button
                          v-for="sound in sampleSounds"
                          :key="`${bank}-${sound}`"
                          class="hs-option"
                          :class="{ selected: isDefaultHitsoundSelected(track, bank, sound) }"
                          type="button"
                          @click.stop="selectDefaultHitsound(trackIndex, bank, sound)"
                        >
                          {{ sound.replace(/^hit/, "") }}
                        </button>
                      </div>
                    </div>
                  </div>

                  <div v-else class="hs-picker-section">
                    <span class="hs-picker-root">custom</span>
                    <div class="lane-mini-controls">
                      <input
                        v-model.number="track.customSampleIndex"
                        min="1"
                        step="1"
                        type="number"
                        title="Custom sample set"
                        @change="handleCustomSampleIndexChange(trackIndex)"
                      />
                      <input
                        class="lane-file-input"
                        accept="audio/*"
                        type="file"
                        title="Upload custom HS"
                        @change="handleSampleUpload($event, trackIndex)"
                      />
                    </div>
                    <div class="hs-bank-grid">
                      <div v-for="bank in sampleBanks" :key="`custom-${bank}`" class="hs-bank-group">
                        <span>{{ bank }}</span>
                        <button
                          v-for="sound in sampleSounds"
                          :key="`custom-${bank}-${sound}`"
                          class="hs-option"
                          :class="{ selected: isCustomHitsoundTypeSelected(track, bank, sound) }"
                          type="button"
                          @click.stop="selectCustomHitsoundType(trackIndex, bank, sound)"
                        >
                          {{ sound.replace(/^hit/, "") }}
                        </button>
                      </div>
                    </div>
                  </div>
                </details>
              </template>

              <template v-else-if="!track.collapsed">
                <input
                  class="lane-file-input"
                  accept="audio/*"
                  type="file"
                  title="Upload one-shot"
                  @change="handleFxClipUpload($event, trackIndex)"
                />
                <span>{{ track.fxClips.length }} clips</span>
                <div v-if="getSelectedFxClip(track)" class="fx-clip-editor">
                  <span class="fx-clip-editor-name">{{ getSelectedFxClip(track)?.name }}</span>
                  <div class="lane-mini-controls">
                    <select
                      :value="getSelectedFxClip(track)?.bank"
                      title="FX sample set"
                      @change="updateSelectedFxClipBank(track, $event)"
                    >
                      <option v-for="bank in sampleBanks" :key="`fx-bank-${bank}`" :value="bank">
                        {{ bank }}
                      </option>
                    </select>
                    <select
                      :value="getSelectedFxClip(track)?.sound"
                      title="FX sample type"
                      @change="updateSelectedFxClipSound(track, $event)"
                    >
                      <option v-for="sound in sampleSounds" :key="`fx-sound-${sound}`" :value="sound">
                        {{ sound.replace(/^hit/, "") }}
                      </option>
                    </select>
                  </div>
                </div>
              </template>
            </div>

            <template v-if="track.channelType === 'fx' && !track.collapsed">
              <button
                v-for="clip in track.fxClips"
                :key="clip.id"
                class="fx-clip"
                :class="{
                  assigned: clip.assignedNoteIndex !== null,
                  selected: selectedFxClipId === clip.id,
                }"
                :style="fxClipStyle(clip)"
                type="button"
                :title="`${clip.name} -> ${clip.bank}-${clip.sound}${clip.assignedNoteIndex !== null ? ` assigned to ${formatTime(notes[clip.assignedNoteIndex]?.timeMs ?? clip.startMs)}` : ''}`"
                @click.stop="selectFxClip(trackIndex, clip)"
                @pointerdown.stop="startFxClipDrag($event, trackIndex, clip)"
                @dblclick.stop="removeFxClip(trackIndex, clip.id)"
              >
                <span>{{ clip.name }}</span>
                <small>{{ clip.bank }}-{{ clip.sound.replace(/^hit/, "") }}</small>
              </button>
            </template>

            <template v-else-if="track.channelType === 'regular'">
              <button
                v-for="note in visibleRegularNotes(track)"
                :key="`${track.id}-${note.id}-placed`"
                class="fx-clip placed-note"
                :class="{
                  assigned: note.assignedNoteIndex !== null,
                  selected: selectedRegularNoteIds.has(getRegularNoteKey(track, note)),
                  active: note.assignedNoteIndex !== null && isNearPlayhead(notes[note.assignedNoteIndex]),
                }"
                :style="regularNoteStyle(note)"
                type="button"
                :aria-label="`${track.name} note at ${formatTime(note.startMs)}`"
                :title="`${track.name} at ${formatTime(note.startMs)}${note.assignedNoteIndex !== null ? `, assigned to ${formatSlotKind(notes[note.assignedNoteIndex]?.kind ?? 'circle')}` : ', not assigned to osu slot'}`"
                @pointerdown.stop="startRegularNoteDrag($event, trackIndex, note)"
                @dblclick.stop="removeRegularNote(trackIndex, note.id)"
              />
            </template>
          </div>
        </div>
      </div>
    </section>

    <section v-if="!notes.length" class="panel empty-panel">
      <h2>Start with an osu file</h2>
      <p>
        Once loaded, the top guide shows the osu rhythm. Double-click regular
        channels to place snapped notes, then drag them like clips.
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

.compact-control input {
  width: 100%;
  border: 1px solid rgba(148, 163, 184, 0.28);
  border-radius: 10px;
  padding: 7px 9px;
  color: #f8fafc;
  background: rgba(15, 23, 42, 0.85);
}

.ghost-button,
.clipboard-controls button,
.lane-actions button,
.lane-pill-button,
.hs-option {
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

.transport {
  flex-wrap: wrap;
  flex: 0 0 auto;
  margin-bottom: 12px;
}

.channel-add-controls {
  display: flex;
  gap: 8px;
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
  width: 280px;
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

.rhythm-preview-lane {
  position: relative;
  z-index: 1;
  height: 38px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.18);
  background: rgba(15, 23, 42, 0.74);
  pointer-events: none;
}

.preview-label {
  display: grid;
  height: 38px;
  place-items: center start;
  padding-left: 18px;
  color: #94a3b8;
  font-size: 0.78rem;
  font-weight: 800;
  background: rgba(15, 23, 42, 0.96);
}

.preview-note {
  position: absolute;
  top: 50%;
  z-index: 2;
  width: 6px;
  height: 18px;
  transform: translate(-50%, -50%);
  border-radius: 999px;
  background: rgba(103, 232, 249, 0.65);
}

.preview-slider-body {
  position: absolute;
  top: 50%;
  z-index: 1;
  height: 10px;
  transform: translateY(-50%);
  border-radius: 999px;
  background: rgba(103, 232, 249, 0.22);
}

.snap-layer {
  position: absolute;
  top: 82px;
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
  height: var(--track-lane-height, 132px);
  border-bottom: 1px solid var(--track-accent-soft, rgba(148, 163, 184, 0.14));
  background:
    linear-gradient(90deg, var(--track-accent-soft, transparent), transparent 34rem),
    repeating-linear-gradient(
      90deg,
      transparent 0 calc(var(--second-width) - 1px),
      rgba(148, 163, 184, 0.1) calc(var(--second-width) - 1px) var(--second-width)
    );
}

.track-lane.collapsed {
  overflow: visible;
}

.track-lane:last-child {
  border-bottom: 0;
}

.track-lane.active {
  box-shadow: inset 0 0 0 2px var(--track-accent-muted, rgba(103, 232, 249, 0.26));
}

.lane-label {
  display: grid;
  align-content: start;
  gap: 6px;
  z-index: 8;
  height: var(--track-lane-height, 132px);
  padding: 10px 12px;
  border-right: 2px solid var(--track-accent, rgba(148, 163, 184, 0.18));
  background:
    linear-gradient(90deg, var(--track-accent-soft, transparent), transparent),
    rgba(15, 23, 42, 0.98);
  box-shadow: 12px 0 18px rgba(2, 6, 23, 0.32);
  cursor: pointer;
}

.track-lane.collapsed .lane-label {
  align-content: center;
  padding: 0 10px;
}

.lane-label span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.lane-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.lane-header span {
  flex: 0 0 auto;
  color: var(--track-accent, #67e8f9);
  font-weight: 800;
  text-transform: uppercase;
}

.lane-icon-button {
  flex: 0 0 auto;
  width: 20px;
  height: 20px;
  border: 1px solid rgba(148, 163, 184, 0.3);
  border-radius: 999px;
  padding: 0;
  color: #e2e8f0;
  background: rgba(15, 23, 42, 0.82);
  font-size: 0.72rem;
  line-height: 1;
}

.lane-pill-button {
  flex: 0 0 auto;
  padding: 4px 8px;
  font-size: 0.68rem;
}

.lane-name-input,
.lane-mini-controls input,
.lane-mini-controls select {
  min-width: 0;
  border: 1px solid rgba(148, 163, 184, 0.28);
  border-radius: 9px;
  padding: 5px 7px;
  color: #f8fafc;
  background: rgba(15, 23, 42, 0.9);
  font-size: 0.75rem;
}

.lane-name-input {
  width: 100%;
  color: var(--track-accent, #f8fafc);
  font-weight: 800;
}

.track-lane.collapsed .lane-name-input {
  border-color: transparent;
  padding: 2px 0;
  background: transparent;
}

.lane-mini-controls,
.lane-actions {
  display: flex;
  gap: 6px;
}

.lane-mini-controls input {
  width: 52px;
}

.lane-mini-controls select {
  flex: 1;
}

.lane-file-input {
  width: 100%;
  color: #cbd5e1;
  font-size: 0.68rem;
}

.fx-clip-editor {
  display: grid;
  gap: 5px;
  padding: 6px;
  border: 1px solid var(--track-accent-muted, rgba(103, 232, 249, 0.36));
  border-radius: 10px;
  background: rgba(2, 6, 23, 0.35);
}

.fx-clip-editor-name {
  color: #e2e8f0;
  font-size: 0.68rem;
  font-weight: 800;
}

.hs-picker {
  display: grid;
  gap: 5px;
  min-width: 0;
}

.hs-picker summary {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  color: #cbd5e1;
  cursor: pointer;
  font-size: 0.72rem;
}

.hs-picker summary strong {
  overflow: hidden;
  min-width: 0;
  color: #f8fafc;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.hs-source-toggle {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 5px;
  padding: 6px;
  border: 1px solid var(--track-accent-muted, rgba(103, 232, 249, 0.36));
  border-radius: 12px;
  background:
    linear-gradient(135deg, var(--track-accent-soft, rgba(103, 232, 249, 0.12)), transparent),
    rgba(2, 6, 23, 0.5);
  box-shadow: inset 0 0 0 1px rgba(15, 23, 42, 0.66);
}

.hs-source-label {
  grid-column: 1 / -1;
  color: var(--track-accent, #67e8f9);
  font-size: 0.62rem;
  font-weight: 900;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.hs-source-toggle button {
  min-width: 0;
  border-color: rgba(148, 163, 184, 0.3);
  padding: 6px 8px;
  background: rgba(15, 23, 42, 0.9);
  font-size: 0.72rem;
  font-weight: 800;
}

.hs-source-toggle button.selected {
  border-color: var(--track-accent, #67e8f9);
  color: #f8fafc;
  background:
    linear-gradient(135deg, var(--track-accent-dark, #0891b2), var(--track-accent-soft, rgba(103, 232, 249, 0.14))),
    rgba(15, 23, 42, 0.92);
  box-shadow: 0 0 0 2px var(--track-accent-soft, rgba(103, 232, 249, 0.14));
}

.hs-picker-section {
  display: grid;
  gap: 4px;
  padding: 5px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 10px;
  background: rgba(15, 23, 42, 0.52);
}

.hs-picker-root,
.hs-bank-group > span {
  color: #94a3b8;
  font-size: 0.68rem;
  font-weight: 800;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.hs-bank-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 4px;
}

.hs-bank-group {
  display: grid;
  gap: 3px;
  min-width: 0;
}

.hs-option {
  overflow: hidden;
  padding: 2px 4px;
  font-size: 0.63rem;
  line-height: 1.05;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.hs-option.selected {
  border-color: var(--track-accent, #67e8f9);
  color: #f8fafc;
  background: var(--track-accent-soft, rgba(103, 232, 249, 0.14));
}

.lane-actions button {
  padding: 4px 8px;
  font-size: 0.7rem;
}

.selection-marquee {
  position: absolute;
  z-index: 6;
  border: 1px solid rgba(103, 232, 249, 0.9);
  background: rgba(103, 232, 249, 0.14);
  box-shadow: 0 0 0 1px rgba(15, 23, 42, 0.4);
  pointer-events: none;
}

.fx-clip {
  position: absolute;
  top: 50%;
  z-index: 3;
  display: grid;
  align-content: center;
  gap: 2px;
  overflow: hidden;
  height: 46px;
  transform: translateY(-50%);
  border: 1px solid var(--track-accent, #67e8f9);
  border-radius: 10px;
  padding: 0 10px;
  color: #f8fafc;
  background:
    linear-gradient(135deg, var(--track-accent-dark, #0891b2), rgba(15, 23, 42, 0.9)),
    repeating-linear-gradient(90deg, rgba(255, 255, 255, 0.2) 0 2px, transparent 2px 8px);
  text-align: left;
  text-overflow: ellipsis;
  white-space: nowrap;
  box-shadow: 0 12px 28px rgba(2, 6, 23, 0.35);
  cursor: grab;
}

.fx-clip small {
  overflow: hidden;
  color: rgba(226, 232, 240, 0.78);
  font-size: 0.62rem;
  text-overflow: ellipsis;
}

.fx-clip.assigned {
  box-shadow:
    0 0 0 3px var(--track-accent-soft, rgba(103, 232, 249, 0.16)),
    0 12px 28px rgba(2, 6, 23, 0.35);
}

.fx-clip.selected {
  border-color: #f8fafc;
  box-shadow:
    0 0 0 3px rgba(248, 250, 252, 0.22),
    0 12px 28px rgba(2, 6, 23, 0.35);
}

.placed-note {
  display: block;
  height: 22px;
  border-radius: 50%;
  padding: 0;
  text-align: center;
}

.placed-note.active {
  border-color: #f97316;
  box-shadow:
    0 0 0 3px rgba(249, 115, 22, 0.2),
    0 12px 28px rgba(2, 6, 23, 0.35);
}

.placed-note.selected {
  border-color: #f8fafc;
  box-shadow:
    0 0 0 3px rgba(248, 250, 252, 0.24),
    0 12px 28px rgba(2, 6, 23, 0.35);
}

.playhead {
  position: absolute;
  top: 82px;
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
