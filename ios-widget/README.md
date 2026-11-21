# iOS widget

A small WidgetKit app that puts LifeDB on the iPhone home screen and lock screen. It reads two
endpoints from the dashboard in this repo (`scripts/dashboard.py`):

- `GET /api/summary` for the stats widget: steps, distance, spending, texts, calls and emails
  over the last seven days.
- `GET /api/insight` for the insight widget: the short AI-written note on the day.

Two widgets ship in one extension. `LifeWidget` comes in medium and lock-screen rectangular sizes;
`InsightWidget` adds a lock-screen inline size. Both refresh every 30 minutes.

## Setup

1. Open `OMAR_WIDGET.xcodeproj` in Xcode.
2. Set your own team and bundle identifiers on both targets. The project ships with the team blank
   and `com.example.LifeWidget` as a placeholder.
3. Put your dashboard's address in **both** copies of `LifeDataClient.swift`
   (`Shared/` for the app, `LifeWidgetExtension/Widget/Shared/` for the widgets). It ships as
   `http://lifedb.example:8080`.
4. Build to your phone, open the app once, and tap **Test connection**.

## Network

The dashboard speaks plain HTTP and has no authentication, so both targets allow arbitrary loads
and the phone must reach the server over a network you control. A private mesh such as Tailscale
is the intended path: the phone keeps reaching the dashboard away from home and nothing is exposed
to the internet. Do not point this at a public address.

## Notes

The app target and the widget extension each carry their own copy of the data client and models;
the extension's copy is the newer one and adds the seven-day period and the insight call. The
Xcode previews use made-up numbers.
