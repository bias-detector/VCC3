# VCC 3 Frontend

Static HTML/CSS/JavaScript frontend for the toxicity classifier UI.

## Architecture

- public/ - Production static files
  - index.html - Main page
  - styles.css - Styling
  - app.js - Client-side logic
- src/ - (Future) Source for build pipeline if moving to React/Vue

## Development

Test locally without backend:

```bash
cd frontend
python3 -m http.server 3000 --directory public
```

Open http://127.0.0.1:3000

## Served From

Backend serves these files at /static/ via FastAPI:

```
GET / -> index.html
GET /static/styles.css -> styles.css
GET /static/app.js -> app.js
```

## Future

- Migrate to React/Vue for components
- Add TypeScript support
- Add build pipeline with Webpack/Vite
- Unit tests for client logic
