# ZakLang playground prototype

React + TypeScript + Vite, with the existing Tailwind, React Router, and TanStack Query setup.

Use Node.js 20.19+ or 22.12+ for the existing Vite toolchain.

```sh
cd playground
npm install
npm run dev
```

Open the URL printed by Vite. `npm run build` creates a production build; `npm run lint` checks the frontend.

## Prototype features

- Playground with the repository’s three public tasks, Zak/Python selection, syntax-highlighted editable code, seed controls, and a staged demo pipeline.
- Explorer with illustrative paired comparisons, language filters, run details, and CSV export.
- Local run history (up to 50 runs in localStorage), draft grammar documentation, and a demo workspace page.
- Responsive dark interface, keyboard focus states, native modal dialogs, and reduced-motion support.

With focus inside the workspace, Cmd+Enter or Ctrl+Enter runs the pipeline. Tab inserts two spaces in the editor; Shift+Tab moves focus out.

The pipeline loads **demo fixtures**, not live inference or compiler responses. Token counts are illustrative. Edited source is accepted by the editor, but only the supplied reference fixtures can advance through the demo. No Python or Zak code is executed in the browser. Hidden test files are not imported, displayed, or bundled. Authentication is not connected.

Public statements and example solutions live in `src/lib/demo.ts`; local history lives in `src/lib/run-store.ts`. The existing `src/lib/api.ts` helper and Query provider are retained for future FastAPI integration. `VITE_API_URL` is reserved for that integration and does not enable a live backend in this prototype.

The reference syntax follows `../compiler/src/grammar.txt` (Zak Core v0.1). The compiler’s grammar remains the source of truth.
