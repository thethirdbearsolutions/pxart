---
# A template for posts: copy it to <slug>.md (lowercase words joined by hyphens).
# It lives outside the posts folder; see site/README.md, "The blog".
title: At most 60 characters, the page's <title> and h1
description: At most 155 characters, the lead under the title and the search snippet.
date: 2026-11-08            # YYYY-MM-DD, the publish date
# updated: 2026-11-20       # when a post is corrected or brought up to date
hub: git                    # git | format | field-notes | builds | craft
tags: [git, review]
related: []                 # up to 3 slugs of other posts, hand-picked
heroSprite: examples/01-format/gem.px   # FILE.px[:frame][%variant]: the preview card
credits: The gem is from tutorial 01.   # who drew what
# byline: Written by Claude for pxart   # the default
# footer: ...                            # the default credits the Claude sessions
track: A                    # A: our posts; B: Ethan's
draft: true                 # built only with PXART_DRAFTS=1
---

No h1: the title is the page's h1. Start with the point.

```px
k #2b1e2f
p #d8718c

..kkk..
.kpppk.
..kkk..
```

```tryme
gem
```

Links to the site are absolute ([the format](/docs/format/)); links to repository files are
written as if the post sat in site/src/content/blog/, and go to GitHub.
