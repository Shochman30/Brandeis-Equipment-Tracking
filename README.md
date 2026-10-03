# Brandeis South Campus Residence Hall – Energization & Startup Tracker

Static copy of the tracker for GitHub Pages (or any static web host). Snapshot exported October 3, 2026.

## Contents
- `index.html` – the tracker (all code and data in one file)
- 68 `.jpg` files – drawings, room plans, FSD maps, mechanical plans and Fred Williams shop drawings. They must sit in the same place as `index.html` (repository root), not in a sub-folder.

## Publish on GitHub Pages
1. Create a new repository on github.com (for example `brandeis-tracker`).
2. Unzip, open the `brandeis-tracker` folder, select ALL files inside it (index.html, README.md and all 68 .jpg files) and drag them onto GitHub's Add file → Upload files page, then Commit. Do not drag the folder itself.
3. Settings → Pages → Build and deployment: Source "Deploy from a branch", Branch `main`, folder `/ (root)` → Save.
4. After a minute or two the site is live at `https://<your-username>.github.io/brandeis-tracker/`.

## What works
- All tabs, filters, plan viewers, shop drawings, the 3D model and the Overall progress view.
- Downloads: PDF reports, the mechanical naming spreadsheet and the 03B Cx checklist.
- Change history tab (password protected).

## What does not
- Shared saving: "Save changes" stores edits only in the browser that made them (they survive reloads there). Other people and other devices don't see them, and clearing browser data erases them. Keep updating the Claude-hosted tracker and export a new copy to refresh this site; when a new copy is uploaded, each browser's saved edits are replaced by the new copy's data.
- Viewer names in Change history and the owner-only password change (these need the Claude-hosted version).

## Privacy
GitHub Pages on free accounts is public: anyone with the link can see the project data, drawings and shop drawings, and public repositories can be found by search. The Change history password is only a light screen – its data is inside index.html. Confirm with Dimeo and Brandeis before publishing.
