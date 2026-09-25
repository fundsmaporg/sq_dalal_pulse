# TIP — live demo page

A single static page that reads the live feed and renders it as prospective customers
would see it. No build step, no dependencies, no server code.

- **Data source:** `https://raw.githubusercontent.com/fundsmaporg/sq_dalal_pulse/main/latest.json`
  (public, CORS-open), re-fetched every 60 seconds.
- **Everything on screen comes from the payload** — nothing is hard-coded, so the page
  is always current with whatever the scheduled runs last published.

## Deploying to Vercel

Import this repository at <https://vercel.com/new>:

- Framework preset: **Other**
- Root directory: leave as `./` — `vercel.json` points Vercel at `web/`
- Build command: leave empty

Or from a terminal at the repository root: `npx vercel --prod`

If Vercel reports it cannot find the output directory, set **Root Directory** to `web`
instead and remove `outputDirectory` from `vercel.json`.

## Note on the data source

This page reads GitHub directly, which is right for a low-traffic demo. Do **not** point
the production mobile app at that URL — it is CDN-cached for ~5 minutes, rate-limited,
and carries no SLA. The app should read from the Signals service, which receives each
update by webhook.
