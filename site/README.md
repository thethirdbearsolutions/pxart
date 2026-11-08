# pxart.thirdbearsolutions.com

The pxart website: guides, the nine tutorials, the command reference and the changelog.
It's a static [Astro](https://astro.build) site, and nearly all of its content is read from
the repository at build time, so the site and the tool can't drift apart:

| On the site | Comes from |
|---|---|
| Docs: Getting started | `site/src/content/getting-started.md` (written for the site) |
| Docs: the format, errors, commands, prior art | the sections of the top-level `README.md` |
| Tutorials | `examples/*/README.md` and their images (copied into `public/examples/` by `npm run sync`) |
| Reference | `site/src/data/reference.json`: `pxart help` for every command and topic |
| Home page samples | `site/src/data/playground.json`: examples run through `pxart extract --inline-palette` |
| Changelog | `CHANGELOG.md` |

`````px` blocks in any of these are drawn in their own palette, with a render beside them
(`src/lib/markdown.ts`). Links between READMEs become links between the site's pages; links
to other files in the repository go to GitHub.

## Working on it

```sh
cd site
npm install
npm run dev        # http://localhost:4321
npm run build      # into dist/
```

When pxart's help text or the sampled examples change, regenerate the data (Python, with
Pillow) and commit it. `tests/test_site.py` fails until you do:

```sh
python3 site/scripts/gen_reference.py
```

The build itself needs only Node 20 or newer, not Python.

## Deploying

The site is set up for Vercel (`vercel.json`). Create a project from this repository with
**Root Directory** set to `site`. Vercel detects Astro, and Astro reads `../README.md` and
`../examples/` during the build. Then add the domain `pxart.thirdbearsolutions.com` to the
project and a `CNAME` record for `pxart` pointing at `cname.vercel-dns.com`.

Cloudflare Pages works the same way: root directory `site`, build command `npm run build`,
output directory `dist`.

## Later

The roadmap on the home page: v2 adds a library of CC0 and CC BY sprites with "add your
own", v3 a browser editor for `.px` files, and v4 joins the two for remixing and sharing.
`src/lib/px.ts` is already shared between the build and the browser, and is where an
editor would start.
