import { expect, mock, test } from 'claude-code/testing'

const TODAY = JSON.stringify({ reviews: [{ key: 'ledger/01-cash-book-week' }], in_progress: { title: 'Pace the nightly price backfill' }, paths: [] })
const WATCH = [
  { event: 'watching', pair: 'quiet' },
  { event: 'requested', pair: 'quiet', id: 7, kind: 'build', target: 'rate-limiter', status: 'queued', ask: 'Build the next question for rate-limiter.' },
  { event: 'requested', pair: 'quiet', id: 6, kind: 'build', target: 'ledger', status: 'claimed', ask: 'Build the next question for ledger.' },
  { event: 'opened', pair: 'quiet', question: 'rate-limiter/00-pace-the-backfill' },
  { event: 'idle', pair: 'quiet', question: 'rate-limiter/00-pace-the-backfill' },
  { event: 'ran', pair: 'off', question: 'rate-limiter/00-pace-the-backfill' },
]

test('the watch stays up, a request wakes the agent, and the status line says what is due', async ($, on) => {
  const status: (string | undefined)[] = []
  const toasts: string[] = []
  const prompts: string[] = []
  let watches = 0
  const clock = mock.clock(on) // holds the mod's timers until the test moves the time

  // Each hook here stands for the engine, beneath the mod.
  on('process.run', () => ({ value: { exitCode: 0, stdout: TODAY, stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }))
  on('process.spawn', async function* () {
    watches += 1
    // A line may span two pieces: cut the stream in the middle of a line.
    const text = WATCH.map(line => JSON.stringify(line)).join('\n') + '\n'

    yield { stream: 'stdout' as const, text: text.slice(0, 50) }
    yield { stream: 'stdout' as const, text: text.slice(50) }

    return { value: { code: 0, signal: null } }
  })
  on('ui.status', (_, e) => (status.push(e.text), { value: undefined }))
  on('ui.toast', (_, e) => (toasts.push(e.text), { value: undefined }))
  on('prompt.submit', (_, e) => (prompts.push(e.text), { text: e.text }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))

  await $.session.start({ cwd: '/', surface: 'desktop', isInteractive: true })
  await clock.settle() // the watch loop runs on after session.start returns

  expect(watches).toBe(1)
  expect(status).toContain('Whetstone: 1 review due, "Pace the nightly price backfill" in progress, agent connected')
  expect(status.at(-1)).toBe('Whetstone: 1 review due, "Pace the nightly price backfill" in progress, watch stopped')
  expect(toasts).toEqual(['Whetstone: build requested for rate-limiter'])
  // The queued request and the idle event wake the agent. A claimed request, an `opened` in quiet mode and anything in off mode do not.
  expect(prompts.length).toBe(2)
  expect(prompts[0]).toContain('Whetstone request 7')
  expect(prompts[1]).toContain('"event":"idle"')
  // The watch ended, so the mod starts it again 5 s later.
  await clock.advance(5000)
  expect(watches).toBe(2)
  // The new watch replays the queued request. The mod does not announce it twice.
  expect(prompts.filter(text => text.includes('Whetstone request 7')).length).toBe(1)
  expect(toasts.length).toBe(1)
})
