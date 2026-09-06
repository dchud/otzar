# Vendored JavaScript

These files are third-party libraries committed to the repository rather
than fetched from a CDN at page load. HTMX and Alpine drive every
interactive part of the site — barcode scanning, queue polling, the
ingest mode bar, dark mode, every htmx swap. A CDN that does not answer
leaves the page rendered and inert, with no error a user can see or
retry, and cataloguing happens at the shelves on whatever wifi is there.

They are served by WhiteNoise from `static/vendor/` and compressed at
`collectstatic` time.

## Files

| File | Package | Version | Source URL | SHA-384 (base64, SRI form) |
|---|---|---|---|---|
| `htmx-2.0.4.min.js` | `htmx.org` | 2.0.4 | `https://unpkg.com/htmx.org@2.0.4` (redirects to `/dist/htmx.min.js`) | `sha384-HGfztofotfshcF7+8n44JQL2oJmowVChPTg48S+jvZoztPfvwD79OC/LTtG6dMp+` |
| `alpine-3.14.8.min.js` | `alpinejs` | 3.14.8 | `https://unpkg.com/alpinejs@3.14.8/dist/cdn.min.js` | `sha384-X9kJyAubVxnP0hcA+AMMs21U445qsnqhnUF8EBlEpP3a42Kh/JwWjlv2ZcvGfphb` |

Both files were also fetched from
`https://cdn.jsdelivr.net/npm/<package>@<version>/<path>` and are
byte-identical to the unpkg copies, which is the check that the bytes
here are the published release and not something a single mirror served.

`htmx.min.js` is the standard build, not `htmx.esm.js` or any extension
bundle. `cdn.min.js` is Alpine's browser build, which registers itself on
`window.Alpine` and starts on `DOMContentLoaded`; the `module.esm.js`
build does neither and is not a drop-in replacement.

The version is part of each filename, so upgrading changes the URL and no
browser holds a stale copy.

## Upgrading

1. Download the new version from the source URL in the table, into a new
   file named for that version.
2. Recompute the hash and confirm the same bytes come back from jsdelivr:
   ```
   curl -sSL -o static/vendor/htmx-<version>.min.js https://unpkg.com/htmx.org@<version>
   openssl dgst -sha384 -binary static/vendor/htmx-<version>.min.js | openssl base64 -A
   ```
3. Update the `<script>` tags in `templates/base.html`, this table, and
   the version assertions in `tests/test_views.py` and
   `tests/e2e/test_asset_delivery.py`.
4. Delete the file for the old version.
5. Run `./scripts/check.sh`. The end-to-end tests load the pages with
   every off-origin request aborted, so a script that did not actually
   get vendored fails there rather than in a browser at the shelves.

## Licences

Neither minified bundle carries a licence banner, so the notices are
reproduced here, beside the files they cover.

`htmx-2.0.4.min.js` — Zero-Clause BSD, per `htmx.org@2.0.4/LICENSE`:

> Permission to use, copy, modify, and/or distribute this software for
> any purpose with or without fee is hereby granted.
>
> THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL
> WARRANTIES WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED
> WARRANTIES OF MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE
> AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL
> DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR
> PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER
> TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR
> PERFORMANCE OF THIS SOFTWARE.

0BSD attaches no attribution condition; the notice is here because a
reader of this directory should be able to see what the terms are
without leaving it.

`alpine-3.14.8.min.js` — MIT, per `alpinejs/alpine` at tag `v3.14.8`:

> Copyright © 2019-2021 Caleb Porzio and contributors
>
> Permission is hereby granted, free of charge, to any person obtaining
> a copy of this software and associated documentation files (the
> "Software"), to deal in the Software without restriction, including
> without limitation the rights to use, copy, modify, merge, publish,
> distribute, sublicense, and/or sell copies of the Software, and to
> permit persons to whom the Software is furnished to do so, subject to
> the following conditions:
>
> The above copyright notice and this permission notice shall be
> included in all copies or substantial portions of the Software.
>
> THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
> EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
> MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
> NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
> LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
> OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
> WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

MIT requires that notice to travel with the code, which is what
committing it here does.
