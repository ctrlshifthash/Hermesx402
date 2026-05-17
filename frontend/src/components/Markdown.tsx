import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/**
 * Ledger-themed Markdown renderer. Turns the agent's GitHub-flavored Markdown
 * answer (headings, tables, bullet lists, **bold**, and bare/`[]()` URLs) into
 * a clean, readable document with real clickable source links — no raw `##`
 * or naked URLs on screen.
 */
export default function Markdown({ children }: { children: string }) {
  return (
    <div className="al-md text-[13.5px] leading-relaxed text-ink-700">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => (
            <h3 className="mt-5 mb-2 font-display text-base font-bold uppercase tracking-wide text-ink first:mt-0">
              {children}
            </h3>
          ),
          h2: ({ children }) => (
            <h3 className="mt-5 mb-2 border-b border-rule/30 pb-1 font-display text-[11px] font-bold uppercase tracking-[0.2em] text-ink-500 first:mt-0">
              {children}
            </h3>
          ),
          h3: ({ children }) => (
            <h4 className="mt-4 mb-1.5 font-display text-sm font-bold text-ink">
              {children}
            </h4>
          ),
          p: ({ children }) => <p className="my-2">{children}</p>,
          ul: ({ children }) => (
            <ul className="my-2 ml-1 list-none space-y-1.5">{children}</ul>
          ),
          ol: ({ children }) => (
            <ol className="my-2 ml-5 list-decimal space-y-1.5">{children}</ol>
          ),
          li: ({ children }) => (
            <li className="relative pl-4 before:absolute before:left-0 before:text-accent before:content-['▸']">
              {children}
            </li>
          ),
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="font-medium text-accent underline decoration-accent/40 underline-offset-2 hover:decoration-accent break-words"
            >
              {children}
            </a>
          ),
          strong: ({ children }) => (
            <strong className="font-semibold text-ink">{children}</strong>
          ),
          code: ({ children }) => (
            <code className="rounded-sm bg-paper-200 px-1 py-0.5 font-mono text-[12px] text-ink">
              {children}
            </code>
          ),
          blockquote: ({ children }) => (
            <blockquote className="my-2 border-l-2 border-accent/40 pl-3 text-ink-500 italic">
              {children}
            </blockquote>
          ),
          hr: () => <hr className="my-4 border-rule/20" />,
          table: ({ children }) => (
            <div className="my-3 overflow-x-auto border border-rule">
              <table className="w-full border-collapse text-[12.5px]">
                {children}
              </table>
            </div>
          ),
          thead: ({ children }) => (
            <thead className="border-b-2 border-rule bg-paper-200">
              {children}
            </thead>
          ),
          th: ({ children }) => (
            <th className="px-3 py-2 text-left font-semibold uppercase tracking-wider text-ink-500 text-[10px]">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="border-b border-rule/20 px-3 py-2 align-top">
              {children}
            </td>
          ),
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
