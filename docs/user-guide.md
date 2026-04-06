# User guide

A guide for catalogers and community members using the otzar catalog.

## Searching the catalog

The search bar is available on the home page and at `/search/`. Type any combination of title, author, subject, or other terms to search across all records.

### Search tips

- **Hebrew and romanized forms both work.** A record cataloged as "משנה תורה" will also appear when you search for "Mishneh Torah."
- **Partial words match.** Searching for "Rambam" will find records with "Rambam" in any field (author variant names, notes, etc.).
- **Try alternate spellings.** Hebrew transliteration varies. If "Soloveitchik" returns nothing, try "Solovetchik" or search by the Hebrew form.
- **Combine terms to narrow results.** Searching "Maimonides philosophy" finds records matching both words.
- **Known limitation:** The search does not handle Hebrew morphology (prefix particles like -ב, -ה, -ל, or construct forms). Search for base words rather than inflected forms.

## Browsing the catalog

The browse page at `/browse/` offers several ways to explore the collection.

### Author browse

Alphabetical list of authors. Variant name forms (Hebrew, romanized, alternate spellings) are grouped under a single author entry. Selecting an author shows all their works in the catalog.

### Title browse

Alphabetical list of all titles across languages. Useful for finding a specific work when you know the title but not the author.

### Subject browse

Browse by subject headings drawn from catalog records (typically Library of Congress subject headings). Selecting a subject shows all records tagged with that heading.

### Publisher browse

Browse by publisher name. Shows where and by whom items were published.

### Date browse

Browse by publication date. Useful for understanding the historical range of the collection.

### Location browse

Browse by physical location in the library (floor, room, shelf). Shows what is shelved where. Helpful for finding items nearby a known location.

### Series browse

Multi-volume sets grouped together, with indication of which volumes are held and any gaps. For example, a 14-volume series might show "2 of 14 held" with specific volume numbers listed.


## Viewing a record

Each catalog record has a detail page showing:

- **Title** (in original script and romanized form, when both are available)
- **Subtitle**, if any
- **Author(s)**, linked to the author browse
- **Publication information**: publisher, place, and date
- **Language**
- **Subject headings**, linked to the subject browse
- **Series membership**, with volume number and link to the full series
- **Physical location(s)** in the library
- **External identifiers**: ISBN, LCCN, VIAF ID, NLI control number
- **Related items**: other works by the same author, items in the same series, items at nearby shelf locations
- **Source MARC record**: the original bibliographic record as retrieved from the external catalog, available for reference

Record URLs include a stable identifier and a human-readable slug, e.g. `/catalog/otzar-3f8a/mishneh-torah-rambam/`. The identifier is the permanent reference; the slug is cosmetic.


## For catalogers

Cataloging features require a login. Go to `/accounts/login/` and sign in with the account provided by your administrator.

Once logged in, the ingest interface is available at `/ingest/`.

### Adding records

There are three ways to add a record. They can be used in any combination for a single item.

#### Manual entry

Go to `/ingest/new/`. Fill in the bibliographic fields (title, author, publisher, date, etc.) directly. Use this when you have the information at hand or when barcode and OCR methods do not produce a match.

#### ISBN barcode scan

Go to `/ingest/scan/`. Use your phone or laptop camera to scan the barcode on a book. The app reads the ISBN from the camera feed and searches external catalogs (National Library of Israel, Library of Congress) for a matching bibliographic record.

If a match is found, review the candidate record and confirm it. If no match is found, you can photograph the title page or enter the record manually.

#### Title page photograph

Go to `/ingest/scan-title/`. Photograph the title page with your phone camera. The image is sent to Claude Vision, which extracts structured metadata: title, author, publisher, place, date, and romanized forms. This metadata drives a search against external catalogs to find matching records.

Best for older materials without ISBNs. The image is resized client-side before upload for speed.

### The review queue

Scans (both barcode and title page) land in a review queue at `/ingest/queue/` rather than being added to the catalog immediately. This supports a workflow where one or more people scan books on their phones while another person reviews and confirms matches on a laptop.

Each item in the queue shows the scanned input alongside candidate matches from external catalogs. For each candidate, you can see key fields (title, author, date, publisher) and expand to view the full MARC record.

From the queue, you can:
- **Confirm** a scan: accept the best candidate match and add it to the catalog.
- **Discard** a scan: reject it if it was a mistake or if no usable match was found.

Discarded scans are cleaned up automatically after 30 days (configurable via the `cleanup_staging` management command).

### Using your phone

The ingest page offers a QR code at `/ingest/qr/` that links directly to the phone scanning interface. Scan the QR code from your phone to open the scanning page, pre-authenticated with your session. No need to type URLs or log in separately on your phone.

Typical workflow:
1. Log in on your laptop.
2. Scan the QR code with your phone.
3. Walk to the shelves and scan barcodes or photograph title pages on your phone.
4. Return to your laptop and review the queue.

### Series

When a record is part of a multi-volume series, you can manage the series at `/ingest/series/<id>/`.

After cataloging one volume, you can indicate which other volumes you hold without repeating the full search for each. For example, after finding volume 1 of a 13-volume set, mark "I have volumes 1, 3, 5, 7" or "I have all 13." The app uses known series metadata (title, publisher, total volumes) to streamline lookup of additional volumes.

Series can be represented with gaps. Browse views show how many volumes are held out of the total.

### Authority matching

When you add a record, the app checks whether the author matches or nearly matches an existing author in the catalog. It uses VIAF authority data to identify variant spellings and transliterations of the same person.

If a near-match is found, you are prompted to confirm: "This looks like the same author as these other items." You can accept the match (linking the new record to the existing author) or create a new author entry.

The authority check is available during ingest at `/ingest/authority-check/`. This keeps author entries consistent across the catalog without requiring knowledge of formal authority control rules.

### Editing a record

To edit an existing record, go to `/ingest/edit/<record-id>/`. This opens the same form as manual entry, pre-filled with the record's current data.


## Physical locations

Each record can have one or more physical locations describing where the item is shelved. Locations are freeform text, not a fixed hierarchy.

For consistency, adopt a convention within your community. A common pattern is:

```
Floor 1, Main Hall, Shelf A
Floor 2, Study Room, Shelf B
Floor 1, Rare Books, Case 1
```

Use whatever scheme makes sense for your space. The location browse view groups items by their location text, so consistent labeling helps items appear together correctly.

If your community later develops a more structured location scheme (building, floor, room, shelf, section), the system can be extended to support it.
