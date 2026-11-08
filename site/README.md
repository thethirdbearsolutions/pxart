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

The site is hosted on Cloudflare Pages (`wrangler.toml`, `public/_headers`). The project's
settings in the Cloudflare dashboard:

- **Root directory:** `site`. Astro reads `../README.md`, `../examples/` and the rest during
  the build, and Pages clones the whole repository, so that works.
- **Build command:** `npm run build`. **Output directory:** `dist`. Node comes from `.nvmrc`.
- **Build watch paths:** `site/**`, `README.md`, `CHANGELOG.md`, `examples/**`, `pxart.py`, so
  pushes that change none of the site's sources don't trigger a deploy.
- **Custom domain:** `pxart.thirdbearsolutions.com`. If thirdbearsolutions.com's DNS is on
  Cloudflare, Pages adds the record itself; otherwise add a `CNAME` for `pxart` pointing at
  `pxart.pages.dev`.

Pull requests get preview deployments at `<branch>.pxart.pages.dev`.

## The blog

Posts are `src/content/blog/<slug>.md`, with YAML frontmatter; `_template.md` shows every field.
The build checks them and fails on a bad one: title at most 60 characters, description at most 155,
`date` as YYYY-MM-DD, `hub` one of `git`, `format`, `field-notes`, `builds`, `craft`, at most three
`related` slugs that exist. `heroSprite` (`FILE.px[:frame][%variant]`, a repository path) becomes the
post's 1200x630 preview card at `/blog/<slug>/og.png`.

`draft: true` posts are built only with `PXART_DRAFTS=1 npm run build`, so a draft never reaches
production. With no published posts, the Blog link, the RSS link and the sitemap entry stay out and
`/blog/` is noindexed. Posts get RSS (`/blog/rss.xml`), hub pages, and BlogPosting JSON-LD.

The body is the same markdown as the docs: ```` ```px ````, ```` ```tryme ```` and ```` ```layers ````
blocks work, the page drops a leading h1, and relative links resolve from `src/content/blog/`.
The plan the posts follow is the BLOG doc in Chaotic ("pxart blog: four tracks").
