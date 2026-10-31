# Samaritan web app

Next.js (App Router), TypeScript strict, Tailwind CSS v4 and shadcn/ui. Phase 1 runs entirely on mock data; there is no backend yet.

```bash
npm install
cp .env.example .env.local   # NEXT_PUBLIC_DATA_SOURCE=mock
npm run dev                  # http://localhost:3000
npm run lint
npm run build
```

- Pages and components get data only through `src/lib/api` (an ESLint rule forbids importing `src/lib/mock`).
- `NEXT_PUBLIC_MOCK_DEMO_MODE=false` removes the passcode prompts from the mock.
- Mock passcode: `demo123`. Mock data resets on a full page reload.
- This Next.js version differs from older ones; read `node_modules/next/dist/docs/` before changing routing or caching.
