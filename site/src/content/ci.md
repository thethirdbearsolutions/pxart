# CI and pre-commit

Because sprites are text, they can be checked like code: on every commit, and on every pull
request. Two commands are made for it.

- **`pxart check`** reads every `.px` and `.map` file you give it (or every one under a folder) and
  exits 1 if any has an error. Each error is printed with its code, its line and the pixel it's at.
- **`pxart diff`** compares renders pixel by pixel and exits 1 when they differ. It proves that a
  converted pack still draws exactly as its PNGs did, or that a refactored file draws as it used to.

```text
ok   art/barrel.px: 16x16 5c
ok   art/gem-shared.px: 9x8 4c
FAIL art/lamp.px: 1 error(s)
     art/lamp.px:13: E_UNKNOWN_KEY (row 8, x=[8]): keys 'q' aren't in the palette
ok   art/palette.px: palette file, 20 key(s), variants dusk
4 files, 2 frames, 0 warnings, 1 failed
```

## pre-commit

With [pre-commit](https://pre-commit.com), this checks each `.px` and `.map` file a commit changes
and stops the commit if one has an error. pre-commit installs pxart into its own environment, so
nothing else needs installing.

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: pxart-check
        name: pxart check
        entry: pxart check
        language: python
        additional_dependencies: ["pxart @ git+https://github.com/thethirdbearsolutions/pxart"]
        files: \.(px|map)$
```

```sh
pre-commit install
```

A file that imports a palette (`@palette palette.px`) is checked with that palette even when only
the sprite changed, because pxart reads the import from beside the file.

## GitHub Actions

This workflow checks everything under `art/` on each push and pull request that touches it, then
draws a sheet of every frame and attaches it to the run, so a reviewer can look at the art without
checking out the branch.

```yaml
# .github/workflows/pxart.yml
name: pxart

on:
  push:
    paths: ["art/**"]
  pull_request:
    paths: ["art/**"]

jobs:
  art:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      # pin a commit for reproducible builds: ...pxart@<sha>
      - run: pip install "pxart @ git+https://github.com/thethirdbearsolutions/pxart"
      # every .px and .map under art/; exits 1 on any error, listing each at its line
      - run: pxart check art/
      # a sheet of every frame, to look at from the run's page
      - run: pxart sheet art/ -o previews/sheet.png
      - uses: actions/upload-artifact@v4
        with:
          name: pxart-previews
          path: previews/
```

## Stricter checks

`check` takes a few options that turn a project's rules into failures:

- **`--palette art/palette.px`**: every color must come from this palette (a `.px`, a `.gpl` or `.hex`
  file, or a text file of `#rrggbb` colors).
- **`--max-colors 16`**: no frame may use more than 16 colors.
- **`--size 32x32`**: every frame must be this size.
- **`--strict`**: unknown `@sections`, and `@anim` or `@still` lines whose group has no frames, are
  errors rather than notes.
- **`--exclude 'wip'`**: leave out files or folders that match, such as work in progress.

```sh
pxart check art/ --palette art/palette.px --max-colors 16 --strict
```

## Proving a conversion lossless

When art comes in from PNGs (a bought pack, an export from another tool), keep the PNGs and let CI
prove the `.px` files still draw them exactly. `diff` pairs each frame with the PNG its row in the
pack's `labels.csv` names, and exits 1 if any pixel differs:

```sh
pxart diff town/ pack/ --labels pack/labels.csv
```

`pxart help recipes` walks through the whole port, from `from-png` to this check
([recipe 1](/reference/topics/recipes/)), and [tutorial 07](/tutorials/07-import/) does it for one
sprite sheet.
