<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref } from "vue"

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
  uninherited: boolean
}

type RawHitObject = {
  sourceIndex: number
  x: number
  y: number
  timeMs: number
  objectType: number
  kind: HitObjectKind
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

const laneLabelWidth = 190
const markerDiameter = 22
const defaultSamples: DefaultSample[] = [
  { name: "drum-hitnormal.wav", url: "/samples/default/drum-hitnormal.wav" },
  { name: "drum-hitclap.wav", url: "/samples/default/drum-hitclap.wav" },
  { name: "drum-hitfinish.wav", url: "/samples/default/drum-hitfinish.wav" },
  { name: "drum-hitwhistle.wav", url: "/samples/default/drum-hitwhistle.wav" },
  { name: "drum-sliderwhistle.wav", url: "/samples/default/drum-sliderwhistle.wav" },
  { name: "normal-hitnormal.wav", url: "/samples/default/normal-hitnormal.wav" },
  { name: "normal-hitclap.wav", url: "/samples/default/normal-hitclap.wav" },
  { name: "normal-hitfinish.wav", url: "/samples/default/normal-hitfinish.wav" },
  { name: "normal-hitwhistle.wav", url: "/samples/default/normal-hitwhistle.wav" },
  { name: "normal-sliderwhistle.wav", url: "/samples/default/normal-sliderwhistle.wav" },
  { name: "soft-hitnormal.wav", url: "/samples/default/soft-hitnormal.wav" },
  { name: "soft-hitclap.wav", url: "/samples/default/soft-hitclap.wav" },
  { name: "soft-hitfinish.wav", url: "/samples/default/soft-hitfinish.wav" },
  { name: "soft-hitwhistle.wav", url: "/samples/default/soft-hitwhistle.wav" },
  { name: "soft-sliderwhistle.wav", url: "/samples/default/soft-sliderwhistle.wav" },
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
const currentTimeMs = ref(0)
const isPlaying = ref(false)
const audioOffsetMs = ref(0)
const snapPlaybackToGrid = ref(true)
const followPlayhead = ref(true)
const backingAudioUrl = ref<string | null>(null)
const backingAudioName = ref("")
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

let trackIdSeed = 0
let tone: ToneNamespace | null = null
let animationFrameId: number | null = null
let backingStartTimeoutId: number | null = null
let players = new Map<number, import("tone").Player>()

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
    hits: Array(noteCount).fill(false),
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

  mapInfo.value = parsed.info
  notes.value = parsed.notes
  timingPoints.value = parsed.timingPoints
  tracks.value = tracks.value.map((track) => ({
    ...track,
    hits: Array(parsed.notes.length).fill(false),
  }))
  currentTimeMs.value = playbackStartMs.value
  input.value = ""
  timelineScroll.value?.scrollTo({ left: 0 })
  await nextTick()
  updateTimelineViewport()
}

function parseOsuFile(text: string) {
  const metadata = new Map<string, string>()
  const editorSettings = new Map<string, string>()
  const difficultySettings = new Map<string, string>()
  const hitObjects: RawHitObject[] = []
  const parsedNotes: OsuNote[] = []
  const parsedTimingPoints: TimingPoint[] = []
  const rawTimingPoints: RawTimingPoint[] = []
  let section = ""
  let audioFilename = ""

  for (const rawLine of text.split(/\r?\n/)) {
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
    }

    if (section === "TimingPoints") {
      const parts = line.split(",")
      const timeMs = Number(parts[0])
      const beatLengthMs = Number(parts[1])
      const meter = Number(parts[2]) || 4
      const uninherited = parts[6] === undefined || parts[6] === "1"

      if (Number.isFinite(timeMs) && Number.isFinite(beatLengthMs)) {
        rawTimingPoints.push({
          timeMs,
          beatLengthMs,
          meter,
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

    if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(timeMs)) {
      continue
    }

    hitObjects.push({
      sourceIndex: hitObjects.length,
      x,
      y,
      timeMs,
      objectType,
      kind,
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
}

function handleDefaultSampleChange(event: Event, trackIndex: number) {
  const select = event.target as HTMLSelectElement

  selectDefaultSample(trackIndex, select.value)
}

function handleSampleUpload(event: Event, trackIndex: number) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  const track = tracks.value[trackIndex]

  if (!file || !track) {
    return
  }

  revokeCustomSample(track)

  players.get(track.id)?.dispose()
  players.delete(track.id)

  track.sampleUrl = URL.createObjectURL(file)
  track.sampleName = file.name
  track.sampleSource = "custom"
  input.value = ""
}

function handleBackingUpload(event: Event) {
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
  backingDurationMs.value = 0
  input.value = ""
}

function handleBackingMetadata() {
  const durationSeconds = backingAudio.value?.duration

  if (durationSeconds && Number.isFinite(durationSeconds)) {
    backingDurationMs.value = durationSeconds * 1_000
  }

  if (backingAudio.value) {
    backingAudio.value.currentTime = playbackStartMs.value / 1_000
  }
}

function addTrack() {
  tracks.value.push(createTrack(`Track ${tracks.value.length + 1}`, notes.value.length))
}

function removeTrack(trackIndex: number) {
  const [track] = tracks.value.splice(trackIndex, 1)

  if (!track) {
    return
  }

  revokeCustomSample(track)

  players.get(track.id)?.dispose()
  players.delete(track.id)
}

function clearTrack(trackIndex: number) {
  const track = tracks.value[trackIndex]

  if (!track) {
    return
  }

  track.hits = Array(notes.value.length).fill(false)
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
  clipboardStatus.value = hasSelection.value
    ? `Selected ${formatTime(selectionStartMs.value)}-${formatTime(selectionEndMs.value)} on ${
        tracks.value[selectionTrackIndex.value ?? 0]?.name ?? "track"
      }.`
    : ""
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

async function togglePlayback() {
  if (isPlaying.value) {
    stopPlayback()
    return
  }

  await startPlayback()
}

async function startPlayback() {
  await startPlaybackFrom(playbackStartMs.value)
}

async function startPlaybackFrom(startTimeMs: number) {
  if (!canPlay.value) {
    return
  }

  const toneApi = await ensureTone()

  stopPlayback()
  await toneApi.start()
  await rebuildPlayers(toneApi)

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
      backingAudio.value.currentTime = playbackStartMs.value / 1_000
    }
  }

  if (resetPlayhead) {
    currentTimeMs.value = playbackStartMs.value
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

function handleTimelineWheel(event: WheelEvent) {
  const scroller = timelineScroll.value

  if (!scroller || event.ctrlKey) {
    return
  }

  event.preventDefault()

  const deltaModeMultiplier = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? scroller.clientWidth : 1
  const dominantDelta =
    Math.abs(event.deltaX) > Math.abs(event.deltaY) ? event.deltaX : event.deltaY

  scroller.scrollLeft += dominantDelta * deltaModeMultiplier
  updateTimelineViewport()
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

onBeforeUnmount(() => {
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
          <p class="eyebrow">osu sample DAW</p>
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

      </div>

      <p v-if="mapInfo?.audioFilename" class="hint upload-hint">
        Referenced audio: <code>{{ mapInfo.audioFilename }}</code>
        <span v-if="backingAudioName"> Loaded: {{ backingAudioName }}</span>
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
        @click="handleTimelineSeek"
        @pointermove="updateRangeSelection"
        @pointerup="finishRangeSelection"
        @pointerleave="finishRangeSelection"
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

    <section v-if="notes.length" class="panel track-panel">
      <div class="section-heading">
        <div>
          <p class="eyebrow">Tracks</p>
          <h2>Assign samples</h2>
        </div>
        <button class="ghost-button" type="button" @click="addTrack">Add track</button>
      </div>

      <div class="track-list">
        <article
          v-for="(track, trackIndex) in tracks"
          :key="track.id"
          class="track-card"
          :class="{ active: trackIndex === activeTrackIndex }"
          @click="setActiveTrack(trackIndex)"
        >
          <input v-model="track.name" class="track-name" aria-label="Track name" />
          <p>{{ trackHitCount(track) }} notes selected</p>
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
:global(body) {
  margin: 0;
  background: #0f172a;
}

:global(*) {
  box-sizing: border-box;
}

.app-shell {
  min-height: 100vh;
  padding: 32px;
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
  margin: 0 auto 20px;
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
  padding: 16px 18px;
}

.upload-summary {
  display: grid;
  gap: 4px;
  min-width: min(540px, 100%);
}

.upload-summary h1 {
  max-width: 760px;
  font-size: clamp(1.4rem, 3vw, 2rem);
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
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 14px;
  margin-top: 18px;
}

.track-card {
  display: grid;
  gap: 10px;
  padding: 16px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 18px;
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
  text-overflow: ellipsis;
  white-space: nowrap;
}

.track-card label {
  display: grid;
  gap: 6px;
}

.track-name,
.compact-control input,
.track-card select {
  width: 100%;
  border: 1px solid rgba(148, 163, 184, 0.28);
  border-radius: 12px;
  padding: 10px 12px;
  color: #f8fafc;
  background: rgba(15, 23, 42, 0.85);
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
  padding: 9px 13px;
  color: #e2e8f0;
  background: rgba(15, 23, 42, 0.8);
}

.daw-panel {
  display: flex;
  flex-direction: column;
  min-height: calc(100vh - 64px);
  width: 100vw;
  max-width: none;
  margin-right: calc(50% - 50vw);
  margin-left: calc(50% - 50vw);
  border-radius: 0;
  overflow: hidden;
}

.transport {
  flex-wrap: wrap;
  margin-bottom: 18px;
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
  scrollbar-width: none;
  -ms-overflow-style: none;
  overscroll-behavior: contain;
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
