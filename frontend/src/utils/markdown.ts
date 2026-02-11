/**
 * Markdown 解析和消毒工具
 * 参考 OpenClaw 实现
 */
import DOMPurify from 'dompurify';
import { marked } from 'marked';

// 配置 marked
marked.setOptions({
  gfm: true,
  breaks: true,
});

// 允许的 HTML 标签
const allowedTags = [
  'a',
  'b',
  'blockquote',
  'br',
  'code',
  'del',
  'em',
  'h1',
  'h2',
  'h3',
  'h4',
  'hr',
  'i',
  'li',
  'ol',
  'p',
  'pre',
  'strong',
  'table',
  'tbody',
  'td',
  'th',
  'thead',
  'tr',
  'ul',
];

// 允许的属性
const allowedAttrs = ['class', 'href', 'rel', 'target', 'title', 'start'];

// 缓存配置
const MARKDOWN_CHAR_LIMIT = 140_000;
const MARKDOWN_PARSE_LIMIT = 200_000;
const MARKDOWN_CACHE_LIMIT = 200;
const MARKDOWN_CACHE_MAX_CHARS = 50_000;

// LRU 缓存
const markdownCache = new Map<string, string>();

let hooksInstalled = false;

function installHooks() {
  if (hooksInstalled) {
    return;
  }
  hooksInstalled = true;

  // 给所有链接添加安全属性
  DOMPurify.addHook('afterSanitizeAttributes', (node) => {
    if (!(node instanceof HTMLAnchorElement)) {
      return;
    }
    const href = node.getAttribute('href');
    if (!href) {
      return;
    }
    node.setAttribute('rel', 'noreferrer noopener');
    node.setAttribute('target', '_blank');
  });
}

function getCachedMarkdown(key: string): string | null {
  const cached = markdownCache.get(key);
  if (cached === undefined) {
    return null;
  }
  // LRU: 移动到最新位置
  markdownCache.delete(key);
  markdownCache.set(key, cached);
  return cached;
}

function setCachedMarkdown(key: string, value: string) {
  markdownCache.set(key, value);
  if (markdownCache.size <= MARKDOWN_CACHE_LIMIT) {
    return;
  }
  // 删除最老的条目
  const oldest = markdownCache.keys().next().value;
  if (oldest) {
    markdownCache.delete(oldest);
  }
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function truncateText(
  text: string,
  limit: number
): { text: string; truncated: boolean; total: number } {
  if (text.length <= limit) {
    return { text, truncated: false, total: text.length };
  }
  return {
    text: text.slice(0, Math.max(0, limit)),
    truncated: true,
    total: text.length,
  };
}

/**
 * 将 Markdown 转换为安全的 HTML
 */
export function toSanitizedMarkdownHtml(markdown: string): string {
  const input = markdown.trim();
  if (!input) {
    return '';
  }

  installHooks();

  // 检查缓存
  if (input.length <= MARKDOWN_CACHE_MAX_CHARS) {
    const cached = getCachedMarkdown(input);
    if (cached !== null) {
      return cached;
    }
  }

  // 截断过长的内容
  const truncated = truncateText(input, MARKDOWN_CHAR_LIMIT);
  const suffix = truncated.truncated
    ? `\n\n… truncated (${truncated.total} chars, showing first ${truncated.text.length}).`
    : '';

  // 超大内容直接作为代码块展示
  if (truncated.text.length > MARKDOWN_PARSE_LIMIT) {
    const escaped = escapeHtml(`${truncated.text}${suffix}`);
    const html = `<pre class="code-block">${escaped}</pre>`;
    const sanitized = DOMPurify.sanitize(html, {
      ALLOWED_TAGS: allowedTags,
      ALLOWED_ATTR: allowedAttrs,
    });
    if (input.length <= MARKDOWN_CACHE_MAX_CHARS) {
      setCachedMarkdown(input, sanitized);
    }
    return sanitized;
  }

  // 正常解析 Markdown
  const rendered = marked.parse(`${truncated.text}${suffix}`) as string;
  const sanitized = DOMPurify.sanitize(rendered, {
    ALLOWED_TAGS: allowedTags,
    ALLOWED_ATTR: allowedAttrs,
  });

  // 缓存结果
  if (input.length <= MARKDOWN_CACHE_MAX_CHARS) {
    setCachedMarkdown(input, sanitized);
  }

  return sanitized;
}
