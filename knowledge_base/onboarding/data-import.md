# Data import

New customers can import up to 100,000 records per CSV upload. Larger files
should use the chunked upload endpoint or split the file client-side.

## Troubleshooting
- "Row 17 has an invalid email": the import aborts on the first malformed
  row. Ask the customer to fix the offending row and retry.
- Duplicate IDs: imports reject duplicates by default. If the customer wants
  dedup-on-import, have them toggle Settings > Import > Prefer latest row.
- Character encoding: only UTF-8 is supported. Excel exports sometimes use
  Windows-1252, which shows up as mojibake in the preview step.
