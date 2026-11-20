import { useRef, type KeyboardEvent, type ReactNode } from "react"

interface PythonCodeEditorProps {
  value: string
  onChange: (value: string) => void
  disabled?: boolean
  minHeightClass?: string
  "aria-label"?: string
}

const KEYWORDS = new Set([
  "False", "None", "True", "and", "as", "assert", "async", "await", "break",
  "class", "continue", "def", "del", "elif", "else", "except", "finally",
  "for", "from", "global", "if", "import", "in", "is", "lambda", "nonlocal",
  "not", "or", "pass", "raise", "return", "try", "while", "with", "yield",
])

const BUILTINS = new Set([
  "abs", "all", "any", "bool", "dict", "enumerate", "filter", "float",
  "input", "int", "isinstance", "len", "list", "map", "max", "min", "open",
  "pow", "print", "range", "reversed", "round", "set", "sorted", "str",
  "sum", "tuple", "type", "zip",
])

const TOKEN_RE =
  /(#[^\n]*|f?(?:"""[\s\S]*?"""|'''[\s\S]*?'''|"(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])*')|\b\d+(?:\.\d+)?\b|@[A-Za-z_]\w*|\b[A-Za-z_]\w*\b)/g

function highlightPythonLine(line: string, lineIndex: number): ReactNode[] {
  const nodes: ReactNode[] = []
  let lastIndex = 0
  let expectDefName = false
  TOKEN_RE.lastIndex = 0

  for (const match of line.matchAll(TOKEN_RE)) {
    const token = match[0]
    const index = match.index ?? 0
    if (index > lastIndex) {
      nodes.push(line.slice(lastIndex, index))
    }

    let className = ""
    if (token.startsWith("#")) {
      className = "text-slate-500 italic"
    } else if (token.startsWith('"') || token.startsWith("'") || token.startsWith('f"') || token.startsWith("f'")) {
      className = "text-emerald-300"
    } else if (token.startsWith("@")) {
      className = "text-teal-300"
    } else if (/^\d/.test(token)) {
      className = "text-amber-300"
    } else if (expectDefName) {
      className = "text-yellow-300 font-semibold"
      expectDefName = false
    } else if (KEYWORDS.has(token)) {
      className = "text-purple-400 font-medium"
      if (token === "def" || token === "class") expectDefName = true
    } else if (BUILTINS.has(token)) {
      className = "text-sky-400"
    }

    if (className) {
      nodes.push(
        <span key={`${lineIndex}-${index}`} className={className}>
          {token}
        </span>
      )
    } else {
      nodes.push(token)
    }

    lastIndex = index + token.length
  }

  if (lastIndex < line.length) {
    nodes.push(line.slice(lastIndex))
  }
  return nodes.length > 0 ? nodes : [" "]
}

export function PythonCodeEditor({
  value,
  onChange,
  disabled = false,
  minHeightClass = "min-h-[340px]",
  "aria-label": ariaLabel = "Editor de código Python",
}: PythonCodeEditorProps) {
  const preRef = useRef<HTMLPreElement>(null)
  const gutterRef = useRef<HTMLDivElement>(null)
  const lines = value.split("\n")

  const syncScroll = (target: HTMLTextAreaElement) => {
    if (preRef.current) {
      preRef.current.scrollTop = target.scrollTop
      preRef.current.scrollLeft = target.scrollLeft
    }
    if (gutterRef.current) {
      gutterRef.current.scrollTop = target.scrollTop
    }
  }

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    const target = event.currentTarget
    const start = target.selectionStart
    const end = target.selectionEnd

    if (event.key === "Tab") {
      event.preventDefault()
      const next = `${value.slice(0, start)}    ${value.slice(end)}`
      onChange(next)
      requestAnimationFrame(() => {
        target.selectionStart = target.selectionEnd = start + 4
      })
      return
    }

    if (event.key === "Enter") {
      event.preventDefault()
      const lineStart = value.lastIndexOf("\n", start - 1) + 1
      const currentLine = value.slice(lineStart, start)
      const indentMatch = currentLine.match(/^\s*/)
      const baseIndent = indentMatch ? indentMatch[0] : ""
      const extraIndent = currentLine.trimEnd().endsWith(":") ? "    " : ""
      const insertion = `\n${baseIndent}${extraIndent}`
      const next = `${value.slice(0, start)}${insertion}${value.slice(end)}`
      onChange(next)
      requestAnimationFrame(() => {
        const cursor = start + insertion.length
        target.selectionStart = target.selectionEnd = cursor
      })
    }
  }

  return (
    <div className={`relative flex w-full overflow-hidden rounded-md border border-[#1E2629] bg-[#0B1012] font-mono text-sm leading-6 ${minHeightClass}`}>
      <div
        ref={gutterRef}
        aria-hidden="true"
        className="w-11 shrink-0 select-none overflow-hidden border-r border-[#1E2629] bg-[#0F1416] py-3 pr-2.5 text-right text-xs leading-6 text-[#5B6B6D]"
      >
        {lines.map((_, index) => (
          <div key={index}>{index + 1}</div>
        ))}
      </div>

      <div className="relative flex-1 overflow-hidden">
        <pre
          ref={preRef}
          aria-hidden="true"
          className="pointer-events-none m-0 h-full w-full overflow-hidden whitespace-pre p-3 font-mono text-sm leading-6 text-[#E2E8F0]"
        >
          {lines.map((line, index) => (
            <div key={index}>{highlightPythonLine(line, index)}</div>
          ))}
        </pre>

        <textarea
          value={value}
          disabled={disabled}
          spellCheck={false}
          autoCapitalize="off"
          autoComplete="off"
          autoCorrect="off"
          aria-label={ariaLabel}
          onScroll={(event) => syncScroll(event.currentTarget)}
          onKeyDown={handleKeyDown}
          onChange={(event) => onChange(event.target.value)}
          className="absolute inset-0 h-full w-full resize-none overflow-auto whitespace-pre bg-transparent p-3 font-mono text-sm leading-6 text-transparent caret-[#2DD4BF] outline-none selection:bg-[#2DD4BF]/25 disabled:cursor-not-allowed disabled:opacity-60"
        />
      </div>
    </div>
  )
}
