import { expect, mock, test } from 'claude-code/testing'

import { dots, layout, logPath, parseProgress, paneColumns, screenColumns, statusOf, wrapLines } from '../hooks/register'

const LOG = [
  '# Progress: demo',
  '',
  '## Verifier (2026-11-06)',
  '- [x] Built it',
  '- [ ] Run the review',
  'Notes: ignore this line',
  '',
  '## Next tasks, in order',
  '- [ ] Write the skill',
].join('\n')

const PANE = {
  plugin: 'progress-timeline',
  component: 'Pane',
  requestId: 'progress-timeline',
  props: {
    title: 'Progress',
    isFocused: false,
    bodyColumns: 50,
    placement: 'dock',
    scroll: { offset: 0, bodyRows: 20 },
    view: {},
  },
} as const

test('parses tasks, dates and ticks, and skips notes', async () => {
  expect(parseProgress(LOG)).toEqual([
    {
      title: 'Verifier',
      date: '2026-11-06',
      steps: [
        { text: 'Built it', isDone: true },
        { text: 'Run the review', isDone: false },
      ],
    },
    {
      title: 'Next tasks, in order',
      date: '',
      steps: [{ text: 'Write the skill', isDone: false }],
    },
  ])
})

test('accepts a capital X and a star bullet', async () => {
  const [task] = parseProgress('## T\n* [X] Done\n')
  expect(task?.steps).toEqual([{ text: 'Done', isDone: true }])
})

test('drops control characters from the file', async () => {
  const [task] = parseProgress('## T\n- [ ] a\u001b[31mb\n')
  expect(task?.steps[0]?.text).toBe('a[31mb')
})

test('steps outside a task and an empty file give no tasks', async () => {
  expect(parseProgress('- [x] orphan\n')).toEqual([])
  expect(parseProgress('')).toEqual([])
})

test('dots mark done, the current step and later steps', async () => {
  expect(dots(parseProgress(LOG))).toEqual([
    ['done', 'now'],
    ['todo'],
  ])
})

test('the pane says so when there is no log', async $ => {
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  expect((await ui.find({ type: 'Text' }))?.text).toBe('No progress log for this chat yet.')
  await ui.unmount()
})

test('each chat reads its own log under the home folder', async () => {
  expect(logPath('/home/me', 'abc-123')).toBe('/home/me/.claude/progress/abc-123.md')
  expect(logPath('/home/me', 'other')).not.toBe(logPath('/home/me', 'abc-123'))
})

test('a session id cannot point outside the progress folder', async () => {
  expect(logPath('/home/me', '../../evil')).toBe('/home/me/.claude/progress/evil.md')
  expect(logPath('/home/me', '')).toBeNull()
  expect(logPath(undefined, 'abc')).toBeNull()
})

const task = (title: string, date: string, isDone = true) => ({
  title,
  date,
  steps: [{ text: 'a', isDone }],
})

test('a badge opens each new date and cards alternate sides', async () => {
  const rows = layout([task('A', 'd1'), task('B', 'd1'), task('C', 'd2')])
  expect(
    rows.map(row => ('badge' in row ? row.badge : `${row.index}${row.side}`)),
  ).toEqual(['d1', '0left', '1right', 'd2', '2left'])
})

test('a task with no date goes under a Planned badge', async () => {
  const [badge] = layout([task('A', '')])
  expect(badge).toEqual({ badge: 'Planned' })
})

test('status comes from the steps', async () => {
  expect(statusOf(['done', 'done'])).toBe('Done')
  expect(statusOf(['done', 'now'])).toBe('In progress')
  expect(statusOf(['todo'])).toBe('Planned')
  expect(statusOf([])).toBe('Planned')
})

test('wrapLines breaks on words and splits a word longer than the width', async () => {
  expect(wrapLines('one two three', 7)).toEqual(['one two', 'three'])
  expect(wrapLines('abcdefgh', 3)).toEqual(['abc', 'def', 'gh'])
})

test('reads the log, draws a card, and the chevron opens its steps', async ($, on) => {
  on('command.register', () => ({ value: { command: 'progress-timeline' } }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('clock.every', () => ({ value: undefined }))
  on('env.get', () => ({ value: '/home/me' }))
  on('session.id', () => ({ value: 'chat-1' }))
  on('fs.exists', () => ({ value: true }))
  on('fs.stat', () => ({ value: { mtimeMs: 1 } }))
  on('fs.read', () => ({ value: LOG }))

  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })

  expect((await ui.find({ type: 'Text', text: /Verifier/ }))?.text).toBe('Verifier')
  expect(await ui.find({ type: 'Text', text: /Run the review/ })).toBeUndefined()
  await ui.press({ key: 'open-0' })
  expect(await ui.find({ type: 'Text', text: /Run the/ })).toBeDefined()
  await ui.press({ key: 'open-0' })
  expect(await ui.find({ type: 'Text', text: /Run the/ })).toBeUndefined()
  await ui.unmount()
})

const world = (on: any, log: () => string, opens: string[]) => {
  on('command.register', () => ({ value: { command: 'progress-timeline' } }))
  on('ui.open', (_: unknown, e: { id: string }) => {
    opens.push(e.id)
    return { value: { isPlaced: true } }
  })
  on('session.start', (_: unknown, e: { cwd: string }) => ({ cwd: e.cwd }))
  on('env.get', () => ({ value: '/home/me' }))
  on('session.id', () => ({ value: 'chat-1' }))
  on('fs.exists', () => ({ value: log() !== '' }))
  on('fs.stat', () => ({ value: { mtimeMs: log().length } }))
  on('fs.read', () => ({ value: log() }))
}

test('no log means no pane at the start', async ($, on) => {
  const opens: string[] = []
  mock.clock(on)
  world(on, () => '', opens)
  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
  expect(opens).toEqual([])
})

test('a new task section opens the pane once', async ($, on) => {
  const opens: string[] = []
  let log = ''
  const clock = mock.clock(on)
  world(on, () => log, opens)
  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
  log = '## Plan\n- [ ] one\n'
  await clock.advance(2000)
  expect(opens).toEqual(['progress-timeline'])
  log += '- [x] two\n'
  await clock.advance(2000)
  expect(opens).toEqual(['progress-timeline'])
  log += '## Second plan\n- [ ] three\n'
  await clock.advance(2000)
  expect(opens).toEqual(['progress-timeline', 'progress-timeline'])
})

test('an approved plan opens the pane and a refused one does not', async ($, on) => {
  const opens: string[] = []
  mock.clock(on)
  world(on, () => '', opens)
  let answer: object = { result: {} }
  on('tool.call', () => answer)
  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
  await $.tool.call({ tool: 'ExitPlanMode' })
  expect(opens).toEqual(['progress-timeline'])
  answer = { deny: 'no' }
  await $.tool.call({ tool: 'ExitPlanMode' }).catch(() => {})
  expect(opens).toEqual(['progress-timeline'])
})

test('the pane asks for a sixth of the screen, within the dock minimum', async () => {
  expect(paneColumns(192)).toBe(32)
  expect(paneColumns(100)).toBe(24)
})

test('the screen is the chat plus the dock, or the whole width inline', async () => {
  expect(screenColumns(141, 38, 'dock')).toBe(180)
  expect(screenColumns(180, 170, 'inline')).toBe(180)
})
