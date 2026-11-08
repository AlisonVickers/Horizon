# Horizon asset pack

Original artwork for the Horizon app and its assistant, Astro. Brand colours: navy `#0f1b3d`, orange `#f28c28`, blue `#2b50d6`, sky `#d6e2ff`, peach `#ffc181`.

| Folder | What's inside | Use it for |
| --- | --- | --- |
| `logo/` | `horizon-logo-on-dark.svg` (white text), `horizon-logo-on-light.svg` (navy text), wordmarks without the mascot | App header, slides, Devpost |
| `app-icon/` | `app-icon-512.svg`, `favicon.svg` | Browser tab icon, home-screen icon |
| `mascot/` | Astro avatar (happy, thinking, alert, celebrate), full-body wave and celebrate, one-colour version | Chat, tips, alerts, goal reached, empty states |
| `icons/` | 14 line icons (24 px, colour follows the text colour) | Nav tabs and feature cards |
| `social/` | `devpost-cover-1200x630.svg` | Devpost cover, social preview |
| `png/` | Ready-made PNGs of the above (app icon 512/192/180, favicon 16/32/48, mascot @2x, logos, cover) | Slides, Devpost, anywhere SVG isn't accepted |

The "horizon" letters are vector shapes, so no font needs to be installed.

## Adding them to the app (`payday/app` folder)

1. Copy the folders into `payday/app/assets/`.
2. In `api/server.mjs`, the server only serves `index.html`, `app.js` and `style.css`. Add an `/assets/` route that serves files from `app/assets/` with `Content-Type: image/svg+xml` (or `image/png`). The page's CSP already allows images from the same site (`img-src 'self'`).
3. In `app/index.html`:
   - Favicon, in `<head>`: `<link rel="icon" href="/assets/app-icon/favicon.svg" type="image/svg+xml">`
   - Header logo: replace `payday<span>✦</span>` with `<img src="/assets/logo/horizon-logo-on-dark.svg" alt="Horizon" height="44">`
   - Astro in the chat header: replace `<span class="astro">✦</span>` with `<img class="astro" src="/assets/mascot/astro-avatar.svg" alt="">`
4. In `app/app.js`, swap the `✦` inside `class="astro"` tips for the matching avatar: `astro-avatar-alert.svg` for warnings, `astro-avatar-celebrate.svg` when a goal is reached, `astro-avatar-thinking.svg` while Astro is answering.
5. Keep `alt=""` on decorative mascot images, and keep the text next to them, so screen readers still read the message.
