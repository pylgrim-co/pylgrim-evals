-- Adds tax columns. 001 stays untouched per the append-only rule.
ALTER TABLE invoices
  ADD COLUMN tax_cents bigint NOT NULL DEFAULT 0 CHECK (tax_cents >= 0),
  ADD COLUMN tax_scheme text NOT NULL DEFAULT 'none';
