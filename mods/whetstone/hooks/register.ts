import type { EngineInterface, Register } from 'claude-code'

// Runs in a Claude Code session opened in the Whetstone folder. It does three things:
// keeps `bin/whetstone watch` alive (so the app shows "Agent connected"), tells you and the
// agent when the app asks for work, and shows what is due in the status line.

type Api = EngineInterface
type Today = { reviews?: unknown[]; in_progress?: { title?: string } | null }
type WatchEvent = { event?: string; pair?: string; id?: number; kind?: string; target?: string; status?: string; ask?: string; result?: string }

const CLI = 'bin/whetstone'
const EVERY = ['opened', 'paused', 'ran', 'hint', 'solution', 'idle']
// Which of the learner's events start a turn, by the pair mode they chose in the app
// (.claude/skills/whetstone-pair/SKILL.md). A request from the app always does.
const WAKES: Record<string, readonly string[]> = {
  off: [],
  quiet: ['ran', 'hint', 'solution', 'idle'],
  coach: EVERY,
  interviewer: EVERY,
}

// ponytail: module variables, so a reload starts them over and can announce a still-queued request once more.
const seen = { due: '', isConnected: false, announced: new Set<number>() }

export function summary(today: Today): string {
  const reviews = today.reviews?.length ?? 0
  const parts = reviews === 0 ? [] : [reviews === 1 ? '1 review due' : `${reviews} reviews due`]

  if (today.in_progress?.title) parts.push(`"${today.in_progress.title}" in progress`)

  return parts.join(', ')
}

function show($: Api): void {
  // The engine labels the line with the mod's name, and a narrow terminal cuts its end: the connection comes first.
  $.ui.status([seen.isConnected ? 'agent connected' : 'watch stopped', seen.due].filter(Boolean).join(', '))
}

async function refresh($: Api): Promise<void> {
  const { exitCode, stdout } = await $.process.run([CLI, 'today', '--json'], { timeoutMs: 60_000 })

  if (exitCode === 0) seen.due = summary(JSON.parse(stdout))
  show($)
}

function handle($: Api, line: string): void {
  let event: WatchEvent

  try {
    event = JSON.parse(line)
  } catch {
    return
  }
  if (event.event === 'watching') {
    seen.isConnected = true
    show($)
  } else if (event.event === 'requested') {
    if (event.status !== 'queued' || event.id === undefined || seen.announced.has(event.id)) return
    seen.announced.add(event.id)
    $.ui.toast(`Whetstone: ${event.kind} requested${event.target ? ` for ${event.target}` : ''}`)
    void $.prompt.submit({
      text: `Whetstone request ${event.id} from the app: ${event.ask ?? `${event.kind} ${event.target ?? ''}`} Handle it with the whetstone-agent skill.`,
    })
  } else if (event.event === 'request-done' || event.event === 'request-failed') {
    $.ui.toast(`Whetstone: ${event.kind} ${event.event === 'request-done' ? 'ready' : 'failed'}${event.result ? `, ${event.result}` : ''}`)
    void refresh($).catch(() => undefined)
  } else if (event.event && (WAKES[event.pair ?? 'quiet'] ?? []).includes(event.event)) {
    void $.prompt.submit({
      text: `Whetstone event (pair mode ${event.pair ?? 'quiet'}): ${line}\nFollow the whetstone-pair skill. If the mode says to stay quiet here, reply with nothing more than "noted".`,
    })
  }
}

// The loop is the watch's life. When the watch ends (the app restarted, Docker stopped),
// start it again: after 5 s at first, then slower, up to once a minute.
async function keep($: Api, waitMs: number): Promise<void> {
  let next = waitMs

  try {
    let rest = ''

    for await (const piece of $.process.spawn({ argv: [CLI, 'watch'] })) {
      if (piece.stream !== 'stdout') continue
      const lines = (rest + piece.text).split('\n')

      rest = lines.pop() ?? ''
      for (const line of lines) if (line.trim()) handle($, line)
      if (seen.isConnected) next = 5_000
    }
  } catch {
    // The watch could not start. Try again below.
  }
  seen.isConnected = false
  show($)
  $.clock.after(next, () => void keep($, Math.min(next * 2, 60_000)))
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    const started = await next(e)

    try {
      await refresh($)
    } catch {
      return started // not a Whetstone folder: bin/whetstone is not here
    }
    $.clock.every(60_000, () => void refresh($).catch(() => undefined))
    void keep($, 5_000)

    return started
  })
}
