# Vendor payment terms

Default vendor payment terms are Net-30 from the invoice date. Customers can
override the default per-vendor in Suppliers > [vendor] > Settings.

## Notes
- Early-pay discounts (2/10 Net-30 etc.) are supported but require the
  vendor to flag the discount on each individual invoice.
- Terms shorter than Net-15 require finance approval on the customer side;
  the system surfaces a warning banner on the vendor record when this is
  set.
- Any override from the default terms logs an entry in the vendor's audit
  trail for SOX compliance.
