# Design Tokens — BW-Work

Extracted from all 12 "Final:" frames on the Pencil canvas. This is the single source of truth for coding.

**Frames covered:**
- Final: 大厅首页 (UvniA) — 1440×900
- Final: 项目详情 (7rqEH) — 1440×900
- Final: 讨论详情 (Bt54U) — 1440×900
- Final: 文档编辑 (uvMNa) — 1440×900
- Final: 讨论详情-运行中 (SNYpS) — 1280×900
- Final: 讨论详情-已完成 (7uLZE) — 1280×900
- Final: 讨论详情-排队中 (BE0ve) — 1280×900
- Final: 新建讨论弹窗 (Bz4KS) — 560×700
- Final: 新建讨论-人员Tab (uUyeg) — 800×700
- Final: 用户菜单 (ytzkC) — 660×700
- Final: 登录注册 (zy6l3) — 1440×900
- Final: 密码验证弹窗 (DeTyl) — 800×500

---

## Colors

### Page Backgrounds

| Token | Value | Usage |
|-------|-------|-------|
| `bg-page` | `#FFFBF5` | Main page background (all full-page frames) |
| `bg-white` | `#FFFFFF` | Cards, panels, top bars, sidebar |
| `bg-search` | `#F5F3F0` | Search box background |

### Brand / Primary

| Token | Value | Usage |
|-------|-------|-------|
| `brand-primary` | `#7C3AED` | Logo, active tabs, FAB, primary buttons, status accents |
| `brand-light` | `#9F67FF` | Gradient end color (login panel) |
| `brand-overlay-sm` | `#7C3AED20` | Agent active ring glow (3px outside stroke) |
| `brand-overlay-md` | `#7C3AED40` | FAB glow shadow |
| `brand-bg-soft` | `#EDE9FE` | Modal backdrop tint (新建讨论 outer frame) |
| `brand-bg-admin` | `#FAF5FF` | Admin section background in dropdown |

### Text

| Token | Value | Usage |
|-------|-------|-------|
| `text-primary` | `#18181B` | Primary text — headings, titles (lobby, discussion) |
| `text-primary-alt` | `#111827` | Headings in queue state |
| `text-heading-doc` | `#1F2937` | Document editor headings |
| `text-heading-modal` | `#1A1A1A` | Modal dialog headings (Geist) |
| `text-dark` | `#2D2D2D` | Dropdown menu items |
| `text-secondary` | `#374151` | Secondary text, back arrows |
| `text-tertiary` | `#52525B` | Icon color (back navigation) |
| `text-muted` | `#6B7280` | Secondary labels, back text, doc editor controls |
| `text-subtle` | `#71717A` | Descriptions, gear icons |
| `text-placeholder` | `#9C9B99` | Search placeholder |
| `text-placeholder-alt` | `#9CA3AF` | Input placeholders, auto-save text, sub-text |
| `text-separator` | `#A1A1AA` | Breadcrumb "/" separator |
| `text-copyright` | `#999999` | Footer copyright (login page) |

### Status — Running / Success

| Token | Value | Usage |
|-------|-------|-------|
| `status-green-dot` | `#22C55E` | Running status indicator dot |
| `status-green-text` | `#16A34A` | "进行中" status label |
| `status-green-bg` | `#F0FDF4` | Running status pill background |
| `status-green-bg-alt` | `#DCFCE7` | "已采纳" pill background |
| `status-green-bg-soft` | `#D1FAE5` | Completed badge background |

### Status — Warning / Pause

| Token | Value | Usage |
|-------|-------|-------|
| `status-amber-bg` | `#FEF3C7` | Auto-pause banner bg, queuing badge bg |
| `status-amber-text` | `#92400E` | Pause banner text |
| `status-amber-icon` | `#D97706` | Pause icon color |

### Status — Error / Danger

| Token | Value | Usage |
|-------|-------|-------|
| `status-red` | `#EF4444` | Logout text, notification badge fill |

### Agent Avatar Colors

| Token | Value | Agent |
|-------|-------|-------|
| `avatar-purple` | `#7C3AED` | Lead Planner / primary agent |
| `avatar-blue` | `#3B82F6` | System Designer / notification dot |
| `avatar-green` | `#22C55E` | Player Advocate |
| `avatar-orange` | `#F97316` | Number Designer |
| `avatar-pink` | `#EC4899` | Operations Analyst |

### UI Surface Colors

| Token | Value | Usage |
|-------|-------|-------|
| `surface-filter-inactive` | `#F0EDE8` | Filter tab inactive, divider lines (lobby) |
| `surface-border-discussion` | `#F0EBE4` | Borders in discussion detail (topBar, sidebar) |
| `surface-border-doc` | `#E5E7EB` | Borders in document editor, sidebar dividers |
| `surface-border-input` | `#D1D5DB` | Input field borders, outline button strokes |
| `surface-divider-light` | `#F3F4F6` | Light dividers (排队中 frame) |
| `surface-result-card` | `#F4F4F5` | Result card background |
| `surface-sidebar-card` | `#FAFAFA` | Sidebar result card, source card |
| `surface-agent-inactive` | `#D1D5DB` | Greyed-out agent avatars (排队中 state) |
| `surface-drag-handle` | `#D4D4D8` | Resizable divider handle |

### Overlays

| Token | Value | Usage |
|-------|-------|-------|
| `overlay-backdrop` | `#00000066` | Full-screen modal backdrop (40% opacity) |
| `overlay-tooltip` | `#1A1918CC` | FAB label tooltip background |
| `shadow-color-card` | `#0000000D` | Lobby cards shadow color (5% opacity) |
| `shadow-color-bar` | `#0000000A` | Top bar shadow color (4% opacity) |
| `shadow-color-modal` | `#00000020` | Modal shadow (12% opacity) |
| `shadow-color-modal-alt` | `#0000001A` | Modal shadow alt (10% opacity) |
| `shadow-color-modal-strong` | `#00000030` | Password modal shadow (19% opacity) |
| `shadow-color-panel` | `#00000012` | Notification panel shadow |
| `shadow-color-dropdown` | `#00000018` | Dropdown shadow |

---

## Typography

### Font Families

| Token | Value | Usage |
|-------|-------|-------|
| `font-brand` | `Outfit` | Logo, navigation tabs, filter tabs |
| `font-body` | `Inter` | All general UI — labels, headings, body text |
| `font-display` | `Geist` | Modal/dialog titles, login form, copyright |
| `font-project` | `Plus Jakarta Sans` | Project header title only |

### Font Sizes

| Token | px | Usage |
|-------|----|-------|
| `text-xs` | 12px | Small labels, tags, captions, version pills |
| `text-sm` | 13px | Filter tab labels, sort button, info text, save text |
| `text-base` | 14px | Body text, secondary labels, breadcrumbs, back text |
| `text-md` | 15px | Sidebar section headings, notification title |
| `text-lg` | 16px | Page/discussion titles, top bar titles |
| `text-xl` | 18px | Modal titles (Geist), queue empty-state heading |
| `text-2xl` | 20px | Project heading, password modal title |
| `text-3xl` | 22px | Main project header title |
| `text-icon-lg` | 48px | Lock icon, queue clock icon |

### Font Weights

| Token | Value | Usage |
|-------|-------|-------|
| `font-normal` | 400 | Body text, descriptions |
| `font-medium` | 500 | Navigation items, status pills, tab labels |
| `font-semibold` | 600 | Section headings, modal titles (Geist), active tabs |
| `font-bold` | 700 | Logo, page titles, discussion title |

### Letter Spacing

| Token | Value | Usage |
|-------|-------|-------|
| `tracking-tight` | -0.5 | Logo text only |

---

## Spacing

### Heights (Fixed Components)

| Component | Height |
|-----------|--------|
| Top Bar / Header | 56px (lobby) / 52px (discussion) |
| Filter Tabs bar | 52px |
| Filter Tab pill | 32px |
| Compact Agent Bar | 56px |
| Auto-Pause Banner | 44px |
| Bottom Bar | 56px |
| Breadcrumb Row | 36px |
| Tab Bar (sidebar) | 44px |
| Producer Input Bar | 52px |
| Page | 900px |

### Padding Patterns

| Context | Padding |
|---------|---------|
| Top bars (horizontal) | `0 24px` or `0 20px` |
| Page grid | `24px` all sides |
| Modal form content | `20px 24px` |
| Modal footer | `16px 24px` |
| Modal header | `60px` height, padding `24px` horizontal |
| Sidebar panels | `20px` all sides |
| Sidebar (doc editor) | `20px` all sides |
| Notification items | `12px 16px` |
| Dropdown menu items | `10px 16px` or `9px 16px` |
| Chat scroll area | `20px 24px` or `24px 28px` |
| Password modal card | `32px 40px 28px 40px` |

### Gap Patterns

| Context | Gap |
|---------|-----|
| Top bar items | 16px |
| Filter tabs | 12px |
| Grid cards (row/col) | 14px |
| Sidebar rows | 12px (discussion), 16px (doc editor) |
| Form fields | 14px |
| Button rows | 12px |
| Avatar group | -8px (overlap) |
| Breadcrumb | 8px |
| Chat messages | 14px or 16px |
| Notification items (dot + content) | 10px |
| User section items | 10px |

### Widths (Fixed Panels)

| Component | Width |
|-----------|-------|
| Full-page frame (desktop) | 1440px |
| Discussion detail frame | 1280px |
| Discussion right sidebar | 380px |
| Doc editor right sidebar | 320px |
| New discussion modal | 520px |
| New discussion 人员Tab modal | 720px |
| Password modal card | 480px |
| Notification panel | 300px |
| User dropdown | 280px |
| Login left panel | 720px |
| Login right panel | 720px |
| Search box | 360px |

---

## Border Radius

| Token | Value | Usage |
|-------|-------|-------|
| `radius-sm` | 4px | Notification dot, drag handle |
| `radius-md` | 8px | Buttons, inputs, small cards, toolbar chips |
| `radius-lg` | 10px | Result cards, source cards |
| `radius-xl` | 12px | Notification panel, agent bar, sidebar result card |
| `radius-2xl` | 16px | Main cards (lobby grid), modals, page frames |
| `radius-3xl` | 24px | Login left panel decoration |
| `radius-pill` | 100px / 999px | Pill badges, filter tabs, circular avatar buttons |

---

## Shadows / Effects

### Top Bars

```css
box-shadow: 0 1px 4px #0000000A;
/* blur: 4, spread: 0, color: rgba(0,0,0,0.04) */
```

### Stage/Project Column Header

```css
box-shadow: 0 1px 3px #0000000A;
/* blur: 3, spread: 0 */
```

### Lobby Grid Cards

```css
box-shadow: 0 2px 12px #0000000D;
/* blur: 12, spread: 0, color: rgba(0,0,0,0.05) */
```

### Notification Panel

```css
box-shadow: 0 8px 24px #00000012;
/* blur: 24, spread: 0, color: rgba(0,0,0,0.07) */
```

### User Dropdown

```css
box-shadow: 0 8px 24px #00000018;
/* blur: 24, spread: 0, color: rgba(0,0,0,0.094) */
```

### Standard Modal Card

```css
box-shadow: 0 8px 32px -4px #00000020;
/* blur: 32, spread: -4, color: rgba(0,0,0,0.125) */
```

### People Tab Modal

```css
box-shadow: 0 8px 32px -4px #0000001A;
/* blur: 32, spread: -4, color: rgba(0,0,0,0.10) */
```

### Password Modal (Strong)

```css
box-shadow: 0 8px 24px -4px #00000030;
/* blur: 24, spread: -4, color: rgba(0,0,0,0.19) */
```

### FAB Button (Double Shadow)

```css
box-shadow:
  0 4px 16px #7C3AED40,   /* brand glow */
  0 2px 6px #0000001A;    /* base shadow */
```

### Agent Active Ring

```css
/* outline stroke: 3px outside, color #7C3AED20 */
outline: 3px solid #7C3AED20;
```

---

## Borders / Strokes

| Context | Style |
|---------|-------|
| Discussion topBar / sidebar | `1px inside #F0EBE4` |
| Lobby notification panel / dropdown | `1px inside #F0EDE8` |
| Document editor borders | `1px inside #E5E7EB` |
| Input fields | `1px inside #D1D5DB` |
| Outline buttons ("预览", "Cancel") | `1px inside #D1D5DB` |
| Primary button ("存档") outline | `1px inside #7C3AED` |
| Avatar overlap ring | `2px inside #FFFFFF` |
| Horizontal dividers | `1px` fill `#F0EDE8`, `#E5E7EB`, or `#F0EBE4` |
| Bottom bar top border | `1px top #F0EDE8` |
| Sidebar left border (doc editor) | `1px left #E5E7EB` |

---

## Gradients

### Login Left Panel

```css
background: linear-gradient(180deg, #7C3AED 0%, #9F67FF 100%);
```

---

## Components

### Filter Tab — Active

```css
background: #7C3AED;
color: #FFFFFF;
font-family: Outfit;
font-size: 13px;
font-weight: 600;
border-radius: 100px;
padding: 6px 16px;
height: 32px;
```

### Filter Tab — Inactive

```css
background: #F0EDE8;
color: #6D6C6A;
font-family: Outfit;
font-size: 13px;
font-weight: 500;
border-radius: 100px;
padding: 6px 16px;
height: 32px;
```

### Primary Button

```css
background: #7C3AED;
color: #FFFFFF;
font-size: 13px;
font-weight: 500;
border-radius: 8px;
padding: 6px 14px;   /* or 10px 24px for modal footer */
```

### Outline Button

```css
background: transparent;
color: #374151;
font-size: 13px;
font-weight: 500;
border-radius: 8px;
border: 1px solid #D1D5DB;
padding: 6px 14px;
```

### Status Pill — Running

```css
background: #F0FDF4;
color: #16A34A;
font-size: 12px;
font-weight: 500;
border-radius: 100px;
padding: 4px 10px;
/* dot: 8×8px circle #22C55E */
```

### Status Pill — Completed

```css
background: #D1FAE5;
font-size: 12px;
font-weight: 500;
border-radius: 12px;
padding: 4px 10px;
```

### Status Pill — Queuing

```css
background: #FEF3C7;
font-size: 12px;
font-weight: 500;
border-radius: 12px;
padding: 4px 10px;
```

### Auto-Pause Banner

```css
background: #FEF3C7;
color: #92400E;
height: 44px;
padding: 0 20px;
/* icon: lucide circle-pause, color #D97706, 18px */
```

### FAB

```css
background: #7C3AED;
width: 56px;
height: 56px;
border-radius: 100px;
box-shadow: 0 4px 16px #7C3AED40, 0 2px 6px #0000001A;
/* icon: lucide plus, #FFFFFF, 24px */
```

### Agent Avatar — Active / Speaking

```css
border-radius: 100px;
outline: 3px solid #7C3AED20;  /* outside */
width: 40px;
height: 40px;
```

### Agent Avatar — Inactive (Queue)

```css
background: #D1D5DB;
border-radius: 50%;
opacity: 0.5;
width: 40px;
height: 40px;
```

### Notification Dot — Unread

```css
background: #3B82F6;
width: 8px;
height: 8px;
border-radius: 4px;
```

### Notification Dot — Read

```css
background: #DADADA;
width: 8px;
height: 8px;
border-radius: 4px;
```

### Notification Badge (Count)

```css
background: #EF4444;
color: #FFFFFF;
width: 20px;
height: 20px;
border-radius: 10px;
font-size: 12px;
font-weight: 600;
```

---

## Layout

### Page Canvas Sizes

| Frame | Width | Height |
|-------|-------|--------|
| Full-page (desktop) | 1440px | 900px |
| Discussion detail (running/done/queue) | 1280px | 900px |

### Discussion Detail — Running Layout (1280px)

```
topBar              52px  (fill_container, border-bottom #F0EBE4)
compactAgentBar     56px  (fill_container, border-bottom #F0EBE4)
autoPauseBanner     44px  (fill_container, #FEF3C7, conditional)
bodyArea            fill  (leftChat fill + dragDivider 6px + rightSidebar 380px)
```

### Discussion Detail — General Layout (1440px)

```
topBar              52px  (fill_container, border-bottom #F0EBE4)
bodyArea            fill  (leftChat fill + sidebar 380px, border-left #F0EBE4)
```

### Document Editor Layout (1440px)

```
topBar              52px  (fill_container, shadow 0 1px 4px #0000000A)
mainBody            fill  (leftEditor fill + rightSidebar 320px, border-left #E5E7EB)
```

### Lobby Layout (1440px)

```
topBar              56px  (fill_container, shadow 0 1px 4px #0000000A)
filterTabs          52px  (fill_container)
gridContainer       fill  (padding 24px, gap 14px, 2 rows × 4 columns)
FAB                 0px   (absolute overlay, position x:1348 y:-80 relative to row)
```

### Project Detail Layout (1440px)

```
breadcrumbRow       36px  (fill_container, padding 0 24px)
headerRow           90px  (fill_container, padding 0 24px, shadow)
stagePipeline       fill  (6 columns, gap 12px, padding 16px 24px)
bottomBar           56px  (fill_container, border-top #F0EDE8)
```

---

## Icon System

All icons use **Lucide** (`lucide` icon font family) unless noted.

| Icon | Name | Size | Color |
|------|------|------|-------|
| Back | `arrow-left` | 20px | `#52525B` or `#374151` |
| Search | `search` | 16px | `#9C9B99` |
| Settings | `settings` | 20px | `#71717A` or `#6B7280` |
| Plus / New | `plus` | 24px | `#FFFFFF` (FAB) |
| Pause | `circle-pause` | 18px | `#D97706` |
| Eye | `eye` | 20px | `#9CA3AF` |
| File result | `file-check` | 14px | `#7C3AED` |
| Sort | `chevron-down` | 14px | `#6D6C6A` |
| More | `ellipsis` | 18px | `#6B7280` |
| Timer | `timer` | 48px | `#7C3AED` |
