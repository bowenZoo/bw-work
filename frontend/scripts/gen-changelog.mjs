#!/usr/bin/env node
/**
 * gen-changelog.mjs
 * 从 git log 自动生成 frontend/src/data/changelog.ts
 *
 * 支持的 conventional commit 类型：
 *   feat   → 新增 (new)
 *   fix    → 修复 (fix)
 *   refactor / improve / perf → 优化 (improve)
 *   BREAKING CHANGE → 变更 (break)
 *
 * 忽略：chore / test / docs / style
 *
 * 版本号规则：最旧的有效日期 = v1.0.0，每新增一个日期 +0.1.0
 */

import { execSync } from 'child_process'
import { writeFileSync } from 'fs'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const gitRoot = execSync('git rev-parse --show-toplevel', { encoding: 'utf8' }).trim()

// --- Commit type mapping -------------------------------------------------
const TYPE_MAP = {
  feat:     'new',
  fix:      'fix',
  refactor: 'improve',
  improve:  'improve',
  perf:     'improve',
  // skipped:
  test:     null,
  docs:     null,
  chore:    null,
  style:    null,
  ci:       null,
  build:    null,
}

// --- Parse git log -------------------------------------------------------
const rawLog = execSync('git log --pretty=format:"%ad|||%s" --date=short', {
  encoding: 'utf8',
  cwd: gitRoot,
}).trim()

const commits = []
for (const line of rawLog.split('\n').filter(Boolean)) {
  const sep = line.indexOf('|||')
  if (sep === -1) continue
  const date    = line.slice(0, sep).trim()
  const subject = line.slice(sep + 3).trim()

  // Skip auto-changelog commits
  if (subject.includes('自动更新更新日志')) continue

  // Parse conventional commit: type(scope): description
  const m = subject.match(/^(\w+)(?:\([^)]+\))?!?:\s*(.+)$/)
  if (!m) continue

  const [, rawType, text] = m
  const type = TYPE_MAP[rawType.toLowerCase()]
  if (!type) continue  // skip chore, test, etc.

  // BREAKING CHANGE → override type to 'break'
  const finalType = subject.includes('BREAKING') ? 'break' : type
  commits.push({ date, type: finalType, text: text.trim() })
}

// --- Group by date (newest first) ----------------------------------------
const byDate = new Map()
for (const c of commits) {
  if (!byDate.has(c.date)) byDate.set(c.date, [])
  byDate.get(c.date).push({ type: c.type, text: c.text })
}

const dates = [...byDate.keys()].sort().reverse()  // newest first

if (dates.length === 0) {
  console.log('[gen-changelog] ⚠️  没有找到可记录的 commit，changelog 未更新')
  process.exit(0)
}

// --- Assign versions: oldest date = v1.0.0, each new date = +0.1.0 -------
const total = dates.length
const entries = dates.map((date, i) => {
  const minor = total - 1 - i  // newest index 0 gets highest minor
  return {
    version: `v1.${minor}.0`,
    date,
    items: byDate.get(date),
  }
})

// --- Generate TypeScript source ------------------------------------------
const ts = `// 此文件由 scripts/gen-changelog.mjs 自动生成，请勿手动编辑
// 更新方式：git commit 后自动触发，或手动运行 pnpm gen:changelog
export interface ChangelogEntry {
  version: string
  date: string
  items: { type: 'new' | 'fix' | 'improve' | 'break'; text: string }[]
}

export const CHANGELOG: ChangelogEntry[] = ${JSON.stringify(entries, null, 2)}
`

const outputPath = resolve(gitRoot, 'frontend/src/data/changelog.ts')
writeFileSync(outputPath, ts, 'utf8')
console.log(`[gen-changelog] ✅ ${entries.length} 个版本条目 → ${outputPath}`)
