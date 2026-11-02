# HoloNet: review zcom.app against the approved design

The HoloNet website lives in `../ZComShare` (Cloudflare Worker `zcom-share`, Hono; server-rendered
pages in `src/web`, routes in `src/routes/web.js`; API reference `docs/api.md`). It is live at
https://zcom.app (share.zcom.app keeps `/api` and redirects pages).

History: the first site (built elsewhere) was rejected as generic: it matched neither Zero
Company nor Den Designer. It was rebuilt in the Den Designer look (commit 3990b98 "HoloNet
website: pages in the Den Designer look", then 85ef192 and f3187cb) from the approved mockups,
boards **WebHome**, **WebListing**, **WebAccount** and **WebMyShares** on the canvas
https://claude.ai/artifact/Qo83uSVbDmV8eexUDT5zAT. I haven't given a verdict on the rebuilt
pages yet.

The Den Designer look: amber accent #F2B84B, condensed caps labels (Barlow Condensed), Sora
headings, Barlow body, translucent dark panels with thin outlines, 6–8 px radii. The in-game
HoloNet window (DeckHolonet board) is the reference for how a build card and its detail read.

## Goal

1. Compare each live page with its board: home, a listing (`/comp/<code>`), account (signed
   in and out), My Shares, and the Dens "coming soon" page. Use the browser tools if available;
   otherwise read the page HTML and CSS. Note every difference that matters (layout,
   type, colour, spacing, missing content, phone width at 390 px).
2. Show me the differences as a short list with your recommendation for each, and wait for my
   answers before changing anything.
3. Fix what I approve, in `src/web` and its assets, with tests (`npm test`).

## Rules

- No new features or pages beyond the boards. If a board conflicts with what the API or the
  Worker can do, ask.
- Keep the API and the pages' URLs stable; the game bridge and shared links depend on them.
- Self-hosted fonts stay self-hosted; no new third-party requests.
- I deploy (`npm run deploy`); don't deploy or run production migrations.
- Don't commit or push unless I ask. Ask before committing anything you didn't write.
- When you stop, say what you checked and what you could not verify (for example, a page that
  needs my Steam sign-in).
