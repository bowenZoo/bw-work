# Design Spec: 大厅首页 (Hall View)

Source frame: `UvniA` — "Final: 大厅首页"

---

## 1. Page Frame

| Property | Value |
|---|---|
| Type | frame |
| Width | 1440 |
| Height | 900 |
| Fill | `#FFFBF5` (warm off-white) |
| Layout | vertical |
| Clip | true |

---

## 2. Top Bar (`OGYef`)

| Property | Value |
|---|---|
| Type | frame |
| Width | fill (1440) |
| Height | 56 |
| Fill | `#FFFFFF` |
| Layout | horizontal |
| Align items | center |
| Padding | top 0 / right 24 / bottom 0 / left 24 |
| Gap | 16 |
| Shadow | outer, color `#0000000A` (black 4%), blur 4, offset x 0 y 1 |

### 2.1 Logo Text

| Property | Value |
|---|---|
| Type | text |
| Content | `BW-Work` |
| Fill | `#7C3AED` |
| Font family | Outfit |
| Font size | 20 |
| Font weight | 700 |
| Letter spacing | -0.5 |

### 2.2 Spacer 1

| Property | Value |
|---|---|
| Type | frame |
| Width | fill_container |
| Height | 1 |

### 2.3 Search Box

| Property | Value |
|---|---|
| Type | frame |
| Width | 360 |
| Height | 36 |
| Fill | `#F5F3F0` |
| Corner radius | 100 (pill) |
| Padding | top 0 / right 14 / bottom 0 / left 14 |
| Gap | 8 |
| Align items | center |

**Search Icon**
| Property | Value |
|---|---|
| Type | icon_font (lucide) |
| Icon | `search` |
| Fill | `#9C9B99` |
| Size | 16 × 16 |

**Placeholder Text**
| Property | Value |
|---|---|
| Type | text |
| Content | `搜索项目或讨论...` |
| Fill | `#9C9B99` |
| Font family | Outfit |
| Font size | 14 |
| Font weight | 400 (normal) |

### 2.4 Spacer 2

| Property | Value |
|---|---|
| Type | frame |
| Width | fill_container |
| Height | 1 |

### 2.5 Right Actions

| Property | Value |
|---|---|
| Type | frame |
| Layout | horizontal |
| Gap | 16 |
| Align items | center |

**Bell Wrap**
| Property | Value |
|---|---|
| Type | frame |
| Width | 24 |
| Height | 24 |
| Layout | none (absolute children) |

- **Bell Icon**: icon_font lucide `bell`, fill `#6D6C6A`, 22 × 22, position x 1 y 1
- **Red Dot**: ellipse, fill `#EF4444`, 8 × 8, position x 14 y 0 (top-right corner)

**Avatar**
| Property | Value |
|---|---|
| Type | frame |
| Width | 32 |
| Height | 32 |
| Fill | `#7C3AED` |
| Corner radius | 100 (circle) |
| Layout | vertical |
| Justify content | center |
| Align items | center |

- **Avatar Initial**: text `V`, fill `#FFFFFF`, Outfit 14px weight 600

---

## 3. Filter Tabs (`MqIBA`)

| Property | Value |
|---|---|
| Type | frame |
| Width | fill (1440) |
| Height | 52 |
| Layout | horizontal |
| Align items | center |
| Padding | top 0 / right 24 / bottom 0 / left 24 |
| Gap | 12 |

### Tab Anatomy

All tabs: `height 32`, `cornerRadius 100`, `padding top 6 / right 16 / bottom 6 / left 16`, `justifyContent center`, `alignItems center`.

| Tab | Label | State | Fill | Text fill | Font |
|---|---|---|---|---|---|
| tabAll | `全部` | **Active** | `#7C3AED` | `#FFFFFF` | Outfit 13px 600 |
| tabProj | `项目` | Inactive | `#F0EDE8` | `#6D6C6A` | Outfit 13px 500 |
| tabDisc | `讨论` | Inactive | `#F0EDE8` | `#6D6C6A` | Outfit 13px 500 |
| tabRunning | `进行中` | Inactive | `#F0EDE8` | `#6D6C6A` | Outfit 13px 500 |
| tabMine | `我参与的` | Inactive | `#F0EDE8` | `#6D6C6A` | Outfit 13px 500 |

### Spacer 3

Width: fill_container, Height: 1 (pushes sort button to right)

### Sort Button (`sortBtn`)

| Property | Value |
|---|---|
| Type | frame |
| Layout | horizontal |
| Gap | 4 |
| Align items | center |

- **Label**: text `最近更新`, fill `#6D6C6A`, Outfit 13px 500
- **Icon**: icon_font lucide `chevron-down`, fill `#6D6C6A`, 14 × 14

---

## 4. Grid Container (`RciqX`)

| Property | Value |
|---|---|
| Type | frame |
| Width | fill (1440) |
| Height | fill_container |
| Layout | vertical |
| Padding | 24 (all sides) |
| Gap | 14 |

Contains two rows (`Row 1`, `Row 2`), each `height: fill_container`, `width: fill_container`, `gap: 14`, with 4 cards side-by-side.

**Computed dimensions** (for implementation reference):
- Available height: 900 − 56 (topbar) − 52 (tabs) − 48 (grid padding top+bottom) − 14 (row gap) = **730px**
- Each row height: 730 / 2 = **365px**
- Available width per row: 1440 − 48 (grid padding left+right) − 42 (3 × 14 gap) = **1350px**
- Each card width: 1350 / 4 = **337.5px**

---

## 5. Card — Common Structure

All 8 cards share this styling:

| Property | Value |
|---|---|
| Type | frame |
| Width | fill_container (~337.5px) |
| Height | fill_container (~365px) |
| Fill | `#FFFFFF` |
| Corner radius | 16 |
| Shadow | outer, color `#0000000D` (black ~5%), blur 12, offset x 0 y 2 |
| Clip | true |
| Layout | vertical |

**Top accent bar** (first child, full-width color strip):
- Type: rectangle
- Width: fill_container
- Height: 4

**Card body** (second child):
- Layout: vertical
- Width: fill_container
- Height: fill_container
- Padding: top 16 / right 18 / bottom 16 / left 18
- Gap: 10

---

## 6. Project Cards (4 cards)

Project cards contain: header row, stage text (optional), progress row, avatars row, status row.

### 6.1 P1 — 智能客服系统

**Accent bar**: fill `#7C3AED`

**Header row** (gap 6, alignItems center, width fill_container):
- Emoji: `📁`, text, fill `#1A1918`, Outfit 16px normal
- Title: `智能客服系统`, fill `#1A1918`, Outfit 15px 600

**Stage text**: `需求分析`, fill `#9C9B99`, Outfit 12px 500

**Progress row** (gap 8, alignItems center, width fill_container):
- Track: frame, height 6, width fill_container, cornerRadius 100, fill `#EDE9FE`, clip true, layout none
  - Fill rect: cornerRadius 100, fill `#7C3AED`, height 6, width 80 (x 0 y 0)
- Percentage: `35%`, fill `#7C3AED`, Outfit 11px 600

**Avatars row** (gap 6, alignItems center, width fill_container):
- Spacer: fill_container
- A: 22 × 22, cornerRadius 100, fill `#7C3AED`, text `A` #FFFFFF Outfit 10px 600
- B: 22 × 22, cornerRadius 100, fill `#D89575`, text `B` #FFFFFF Outfit 10px 600
- C: 22 × 22, cornerRadius 100, fill `#3D8A5A`, text `C` #FFFFFF Outfit 10px 600

**Status row** (gap 8, alignItems center, width fill_container):
- Status pill: cornerRadius 100, fill `#EDE9FE`, padding top 3 / right 10 / bottom 3 / left 10, gap 4, alignItems center
  - Dot: ellipse 6 × 6, fill `#7C3AED`
  - Label: `进行中`, fill `#7C3AED`, Outfit 11px 500
- Spacer: fill_container
- Time: `2小时前`, fill `#9C9B99`, Outfit 11px normal

---

### 6.2 P2 — 电商推荐引擎

**Accent bar**: fill `#7C3AED`

**Header row**: emoji `📁`, title `电商推荐引擎`, Outfit 15px 600, fill `#1A1918`

**Stage text**: `概念设计`, fill `#9C9B99`, Outfit 12px 500

**Progress row**:
- Track: fill `#EDE9FE`, height 6
- Fill: fill `#7C3AED`, width 140
- Percentage: `60%`, fill `#7C3AED`, Outfit 11px 600

**Avatars row** (gap 4):
- Spacer: fill_container
- D: fill `#6366F1`
- E: fill `#F59E0B`
- F: fill `#EC4899`
- G: fill `#14B8A6`
- H: fill `#8B5CF6`
- (all: 22 × 22, cornerRadius 100, initial letter #FFFFFF Outfit 10px 600)

**Status row**:
- Pill: fill `#EDE9FE`, dot `#7C3AED`, text `进行中` fill `#7C3AED`, Outfit 11px 500
- Time: `昨天`, fill `#9C9B99`, Outfit 11px normal

---

### 6.3 P3 — 数据分析平台

**Accent bar**: fill `#7C3AED`

**Header row**: emoji `📁`, title `数据分析平台`

**Stage text**: *(none — this card has no stage text element)*

**Progress row**:
- Track: fill `#D1FAE5` (green track), height 6
- Fill: fill `#3D8A5A`, width 230
- Percentage: `100%`, fill `#3D8A5A`, Outfit 11px 600

**Avatars row** (gap 4):
- Spacer: fill_container
- I: fill `#7C3AED`
- J: fill `#F59E0B`
- K: fill `#EC4899`
- L: fill `#3D8A5A`

**Status row**:
- Pill: fill `#D1FAE5`, dot fill `#3D8A5A`, text `已完成` fill `#3D8A5A`, Outfit 11px 500
- Time: `3天前`, fill `#9C9B99`, Outfit 11px normal

---

### 6.4 P4 — AI写作助手

**Accent bar**: fill `#7C3AED`

**Header row**: emoji `📁`, title `AI写作助手`

**Stage text**: `需求分析`, fill `#9C9B99`, Outfit 12px 500

**Progress row**:
- Track: fill `#EDE9FE`, height 6
- Fill: fill `#7C3AED`, width 35
- Percentage: `15%`, fill `#7C3AED`, Outfit 11px 600

**Avatars row** (gap 4):
- Spacer: fill_container
- M: fill `#6366F1`
- N: fill `#D89575`

**Status row**:
- Pill: fill `#EDE9FE`, dot `#7C3AED`, text `进行中` fill `#7C3AED`, Outfit 11px 500
- Time: `刚刚`, fill `#9C9B99`, Outfit 11px normal

---

## 7. Discussion Cards (4 cards)

Discussion cards contain: header row, project tag, live status row, bottom row (time).

### Discussion Card — Common Body

Same card shell as project cards (cornerRadius 16, fill white, shadow, padding [16,18], gap 10).

**Header row** (gap 6, alignItems center):
- Emoji: `💬`, text, fill `#1A1918`, Outfit 16px normal
- Title: fill `#1A1918`, Outfit 15px 600

**Project tag** (cornerRadius 6, fill `#F0EDE8`, padding top 2 / right 8 / bottom 2 / left 8, alignItems center):
- Text: project name, fill `#6D6C6A`, Outfit 11px 500

**Live status row** (gap 6, alignItems center, width fill_container):
- Dot: ellipse 8 × 8
- Status text: Outfit 12px normal, textGrowth fixed-width on fill_container

**Bottom row** (alignItems center, width fill_container):
- Spacer: fill_container
- Time text: fill `#9C9B99`, Outfit 11px normal

---

### 7.1 D1 — 用户画像讨论

**Accent bar**: fill `#3D8A5A`

- Title: `用户画像讨论`
- Tag: `智能客服系统`
- Live dot: fill `#3D8A5A`
- Status text: `3人·产品策划师发言中...`, fill `#6D6C6A`
- Time: `14:40`

---

### 7.2 D2 — 技术方案评审

**Accent bar**: fill `#3D8A5A`

- Title: `技术方案评审`
- Tag: `电商推荐引擎`
- Live dot: fill `#3D8A5A`
- Status text: `4人`, fill `#6D6C6A`
- Time: `1小时前`

---

### 7.3 D3 — 竞品分析报告

**Accent bar**: fill `#9C9B99` (gray — completed)

- Title: `竞品分析报告`
- Tag: `智能客服系统`
- Live dot: fill `#9C9B99`
- Status text: `2人·已完成`, fill `#9C9B99` (muted, not green)
- Time: `昨天`

---

### 7.4 D4 — 移动端交互讨论

**Accent bar**: fill `#3D8A5A`

- Title: `移动端交互讨论`
- Tag: `移动端重构`
- Live dot: fill `#3D8A5A`
- Status text: `5人`, fill `#6D6C6A`
- Time: `刚刚`

---

## 8. Grid Layout — Card Positions

**Row 1 (top row):**

| Position | Card | Accent color |
|---|---|---|
| Col 1 | P1 智能客服系统 (Project) | `#7C3AED` purple |
| Col 2 | D1 用户画像讨论 (Discussion) | `#3D8A5A` green |
| Col 3 | P2 电商推荐引擎 (Project) | `#7C3AED` purple |
| Col 4 | D2 技术方案评审 (Discussion) | `#3D8A5A` green |

**Row 2 (bottom row):**

| Position | Card | Accent color |
|---|---|---|
| Col 1 | P3 数据分析平台 (Project) | `#7C3AED` purple |
| Col 2 | D3 竞品分析报告 (Discussion) | `#9C9B99` gray |
| Col 3 | P4 AI写作助手 (Project) | `#7C3AED` purple |
| Col 4 | D4 移动端交互讨论 (Discussion) | `#3D8A5A` green |

---

## 9. FAB (Floating Action Button)

The FAB layer (`kZwCK`) is `height: 0`, `width: fill_container`, `layout: none` — it acts as an overlay positioned at the bottom of the vertical stack. Its children use absolute positioning relative to the frame.

### FAB Button (`Trpuz`)

| Property | Value |
|---|---|
| Type | frame |
| Width | 56 |
| Height | 56 |
| Fill | `#7C3AED` |
| Corner radius | 100 (circle) |
| Justify content | center |
| Align items | center |
| Position | x 1348, y -80 (bottom-right of page, visually ~20px from right, ~24px from bottom) |
| Shadow 1 | outer, color `#7C3AED40` (purple 25%), blur 16, offset x 0 y 4 |
| Shadow 2 | outer, color `#0000001A` (black 10%), blur 6, offset x 0 y 2 |

**Plus Icon**: icon_font lucide `plus`, fill `#FFFFFF`, 24 × 24

### FAB Tooltip (`Mc5ot`)

| Property | Value |
|---|---|
| Type | frame |
| Fill | `#1A1918CC` (dark, ~80% opacity) |
| Corner radius | 8 |
| Padding | top 4 / right 10 / bottom 4 / left 10 |
| Position | x 1354, y -18 (above FAB center) |

**Label**: text `新建`, fill `#FFFFFF`, Outfit 12px 500

---

## 10. Color Tokens Summary

| Token | Hex | Usage |
|---|---|---|
| Brand Purple | `#7C3AED` | Logo, active tab, project accent, progress fill, FAB |
| Brand Purple Light | `#EDE9FE` | Progress track (in-progress), status pill background |
| Brand Purple Glow | `#7C3AED40` | FAB shadow |
| Brand Green | `#3D8A5A` | Discussion accent (active), completed project progress |
| Brand Green Light | `#D1FAE5` | Completed progress track, completed pill background |
| Page BG | `#FFFBF5` | Page background |
| Surface | `#FFFFFF` | Top bar, cards |
| Input BG | `#F5F3F0` | Search box fill |
| Tab Inactive | `#F0EDE8` | Inactive tab, discussion tag fill |
| Text Primary | `#1A1918` | Card titles, emojis |
| Text Secondary | `#6D6C6A` | Inactive tab labels, discussion status text, sort button |
| Text Tertiary | `#9C9B99` | Placeholder, stage text, time stamps, search icon |
| Danger Red | `#EF4444` | Notification red dot |
| Indigo | `#6366F1` | Avatar color variant |
| Amber | `#F59E0B` | Avatar color variant |
| Pink | `#EC4899` | Avatar color variant |
| Teal | `#14B8A6` | Avatar color variant |
| Violet | `#8B5CF6` | Avatar color variant |
| Terracotta | `#D89575` | Avatar color variant |
| Dark Overlay | `#1A1918CC` | FAB tooltip background |

---

## 11. Typography Summary

| Style | Font | Size | Weight | Usage |
|---|---|---|---|---|
| Logo | Outfit | 20px | 700 | "BW-Work" |
| Search placeholder | Outfit | 14px | 400 | Placeholder text |
| Tab label (active) | Outfit | 13px | 600 | Active tab |
| Tab label (inactive) | Outfit | 13px | 500 | Inactive tabs, sort button |
| Avatar initial (main) | Outfit | 14px | 600 | Top bar user avatar |
| Card title | Outfit | 15px | 600 | Card titles |
| Card emoji | Outfit | 16px | 400 | 📁 / 💬 emojis |
| Card stage | Outfit | 12px | 500 | Stage sub-label |
| Progress % | Outfit | 11px | 600 | "35%", "60%", etc. |
| Status pill | Outfit | 11px | 500 | "进行中", "已完成" |
| Discussion status | Outfit | 12px | 400 | Live agent count/status |
| Card tag | Outfit | 11px | 500 | Project name tag in discussion |
| Time stamp | Outfit | 11px | 400 | Relative time |
| Avatar letter (card) | Outfit | 10px | 600 | Stacked avatar initials |
| FAB tooltip | Outfit | 12px | 500 | "新建" |

---

## 12. Shadow Definitions

| Name | Type | Color | Blur | Offset |
|---|---|---|---|---|
| Top Bar | outer | `#0000000A` | 4 | x 0, y 1 |
| Card | outer | `#0000000D` | 12 | x 0, y 2 |
| FAB Purple glow | outer | `#7C3AED40` | 16 | x 0, y 4 |
| FAB base | outer | `#0000001A` | 6 | x 0, y 2 |
