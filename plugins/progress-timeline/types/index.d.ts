export type Step = { text: string; isDone: boolean }
export type Task = { title: string; date: string; steps: Step[] }

declare module 'claude-code' {
  interface PluginState {
    'progress-timeline': { tasks: Shaped<Task[]>; expanded: string[] }
  }
}
