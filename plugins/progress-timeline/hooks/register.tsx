import { atom, read, update } from 'claude-code'
import type { Register } from 'claude-code'

import type { Task } from '../types'

const PANE = 'progress-timeline'
const TICK_MS = 2000
const SCREEN_SHARE = 6
const MIN_COLUMNS = 24
const DOCK_EDGE = 1
const HEADING = /^##\s+(.+?)\s*$/
const DATED = /^(.*?)\s*\((\d{4}-\d{2}-\d{2})\)$/
const STEP = /^\s*[-*]\s+\[([ xX])\]\s+(.+?)\s*$/
const CONTROL = /[\u0000-\u001f\u007f-\u009f]/g
const MARK = { done: '●', now: '◉', todo: '○' } as const
const COLOR = { done: 'green', now: 'yellow', todo: 'gray' } as const

const STATUS_COLOR = { Done: 'green', 'In progress': 'yellow', Planned: 'gray' } as const
const LINE = 3
const MIN_TWO_SIDES = 44
const CARD_ROWS = 4
const CARD_INSET = 6 // two borders, two padding, a dot and its space
const DOT_ROW = 1

type Dot = keyof typeof MARK
type Status = keyof typeof STATUS_COLOR
type Row = { badge: string } | { index: number; side: 'left' | 'right' }

const tasks = atom({ plugin: 'progress-timeline', key: 'tasks' } as const, [], {
  shape: 'tasks-1',
})
const expanded = atom(
  { plugin: 'progress-timeline', key: 'expanded' } as const,
  [] as string[],
)

export function parseProgress(text: string): Task[] {
  const found: Task[] = []
  for (const raw of text.split('\n')) {
    const line = raw.replace(CONTROL, '')
    const heading = HEADING.exec(line)
    const step = STEP.exec(line)
    if (heading) {
      const dated = DATED.exec(heading[1])
      found.push({
        title: dated ? dated[1] : heading[1],
        date: dated ? dated[2] : '',
        steps: [],
      })
    } else if (step && found.length > 0) {
      found[found.length - 1].steps.push({
        text: step[2],
        isDone: step[1] !== ' ',
      })
    }
  }

  return found
}

/** One state per step, grouped by task. The first open step is the current one. */
export function dots(list: Task[]): Dot[][] {
  let hasCurrent = false

  return list.map(task =>
    task.steps.map(step => {
      if (step.isDone) {
        return 'done'
      }
      const state: Dot = hasCurrent ? 'todo' : 'now'
      hasCurrent = true

      return state
    }),
  )
}

export function statusOf(states: Dot[]): Status {
  if (states.length > 0 && states.every(state => state === 'done')) {
    return 'Done'
  }

  return states.some(state => state !== 'todo') ? 'In progress' : 'Planned'
}

/** Word wrap by hand, so the line beside a card can be exactly as tall as the card. */
export function wrapLines(text: string, width: number): string[] {
  const lines: string[] = []
  let line = ''
  for (const word of text.split(' ')) {
    const joined = line ? `${line} ${word}` : word
    if (joined.length <= width) {
      line = joined
      continue
    }
    if (line) {
      lines.push(line)
    }
    let rest = word
    while (rest.length > width) {
      lines.push(rest.slice(0, width))
      rest = rest.slice(width)
    }
    line = rest
  }

  return line ? [...lines, line] : lines
}

/** The picture from top to bottom: date badges, then cards on alternating sides. */
export function layout(list: Task[]): Row[] {
  const rows: Row[] = []
  let badge: string | null = null
  list.forEach((task, index) => {
    const label = task.date || 'Planned'
    if (label !== badge) {
      badge = label
      rows.push({ badge })
    }
    rows.push({ index, side: index % 2 === 0 ? 'left' : 'right' })
  })

  return rows
}

/** Each chat logs to ~/.claude/progress/<session id>.md, the path the progress-log skill gives it. */
export function logPath(home: string | undefined, sessionId: string): string | null {
  const safe = sessionId.replace(/[^A-Za-z0-9_-]/g, '').slice(0, 64)

  return home && safe ? `${home}/.claude/progress/${safe}.md` : null
}

async function findLog($: any): Promise<string | null> {
  const path = logPath(await $.env.get('HOME'), await $.session.id())

  return path && (await $.fs.exists(path)) ? path : null
}

let seen = ''
let known = 0
let columns: number | undefined

export function paneColumns(screen: number): number {
  return Math.max(MIN_COLUMNS, Math.floor(screen / SCREEN_SHARE))
}

/** The viewport is the chat alone while docked, so add the dock back. */
export function screenColumns(chat: number, body: number, placement: string): number {
  return placement === 'dock' ? chat + body + DOCK_EDGE : chat
}

async function showPane($: any) {
  await $.ui.open({ id: PANE, title: 'Progress', columns })
}

/** Read the log when it changes. A new task section is a new plan, so show it. */
async function refresh($: any) {
  const path = await findLog($)
  const stamp = path ? `${path}:${(await $.fs.stat(path)).mtimeMs}` : 'none'
  if (stamp === seen) {
    return
  }
  seen = stamp
  const text = path ? await $.fs.read(path) : ''
  const list = parseProgress(text)
  await update($, tasks, () => list)
  if (list.length > known) {
    await showPane($)
  }
  known = list.length
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: 'progress-timeline',
      description: 'Show the progress log of this chat as a timeline in a pane',
    })
    await refresh($)
    $.clock.every(TICK_MS, () => refresh($))

    return next(e)
  })

  on('tool.call', { tool: 'ExitPlanMode' }, async ($, e, next) => {
    const ran = await next(e)
    if (!ran.deny && !ran.isError) {
      await refresh($)
      await showPane($)
    }

    return ran
  })

  on('command.run', { command: 'progress-timeline' }, async $ => {
    await showPane($)

    return { text: 'Progress pane opened.' }
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Button, Text } = $.ui.resolve(e)
    // The terminal's width is known only here, so the first draw sets the pane's size.
    const wanted = e.viewport
      ? paneColumns(screenColumns(e.viewport.columns, e.props.bodyColumns, e.props.placement))
      : undefined
    if (wanted !== columns) {
      columns = wanted
      await showPane($)
    }
    const list = await read($, tasks)
    if (list.length === 0) {
      return <Text dimColor>No progress log for this chat yet.</Text>
    }
    const open = await read($, expanded)
    const groups = dots(list)
    const bodyColumns = e.props.bodyColumns
    const isStacked = bodyColumns < MIN_TWO_SIDES
    const sideWidth = Math.floor((bodyColumns - LINE) / 2)
    const toggle = (title: string) =>
      update($, expanded, now =>
        now.includes(title) ? now.filter(one => one !== title) : [...now, title],
      )
    const rail = (text: string) => (
      <Box width={LINE} justifyContent="center">
        <Text dimColor>{text}</Text>
      </Box>
    )
    const gap = (
      <Box>
        {!isStacked && <Box width={sideWidth} />}
        {rail('│')}
      </Box>
    )

    return (
      <Box flexDirection="column">
        {layout(list).map(row => {
          if ('badge' in row) {
            return (
              <Box flexDirection="column">
                {gap}
                <Box
                  width={isStacked ? bodyColumns : sideWidth * 2 + LINE}
                  justifyContent={isStacked ? 'flex-start' : 'center'}
                >
                  <Text backgroundColor="blue" color="white">{` ${row.badge} `}</Text>
                </Box>
                {gap}
              </Box>
            )
          }
          const task = list[row.index]
          const states = groups[row.index]
          const status = statusOf(states)
          const done = states.filter(state => state === 'done').length
          const isOpen = open.includes(task.title)
          const cardWidth = isStacked ? bodyColumns - LINE : sideWidth
          const stepRows = isOpen
            ? task.steps.map((step, index) => ({
                lines: wrapLines(step.text, cardWidth - CARD_INSET),
                state: states[index],
                isDone: step.isDone,
              }))
            : []
          const height = stepRows.reduce((sum, step) => sum + step.lines.length, CARD_ROWS)
          const isLeft = row.side === 'left' && !isStacked
          const dot: Dot = status === 'Done' ? 'done' : status === 'Planned' ? 'todo' : 'now'
          const card = (
            <Box
              width={cardWidth}
              flexDirection="column"
              borderStyle="round"
              borderColor="gray"
              paddingX={1}
            >
              <Box columnGap={1}>
                <Box flexGrow={1}>
                  <Text bold wrap="truncate-end">{task.title}</Text>
                </Box>
                <Button
                  key={`open-${row.index}`}
                  plain
                  dimColor
                  label={isOpen ? '⌄' : '›'}
                  onPress={() => toggle(task.title)}
                />
              </Box>
              <Text dimColor wrap="truncate-end">
                {task.date || 'No date'} · {done}/{states.length}
              </Text>
              {stepRows.flatMap(step =>
                step.lines.map((text, index) => (
                  <Text dimColor={step.isDone}>
                    {index === 0 ? `${MARK[step.state]} ` : '  '}
                    {text}
                  </Text>
                )),
              )}
            </Box>
          )
          const label = (
            <Box
              width={sideWidth}
              paddingTop={DOT_ROW}
              paddingX={1}
              justifyContent={isLeft ? 'flex-start' : 'flex-end'}
            >
              <Text color={STATUS_COLOR[status]}>{status}</Text>
            </Box>
          )
          const line = (
            <Box width={LINE} flexDirection="column">
              {Array.from({ length: height }, (_, index) =>
                index === DOT_ROW ? (
                  <Box justifyContent="center">
                    <Text dimColor>{isLeft ? '─' : ' '}</Text>
                    <Text color={COLOR[dot]}>{MARK[dot]}</Text>
                    <Text dimColor>{isLeft ? ' ' : '─'}</Text>
                  </Box>
                ) : (
                  rail('│')
                ),
              )}
            </Box>
          )

          if (isStacked) {
            return (
              <Box>
                {line}
                {card}
              </Box>
            )
          }

          return (
            <Box>
              {isLeft ? card : label}
              {line}
              {isLeft ? label : card}
            </Box>
          )
        })}
      </Box>
    )
  })
}
