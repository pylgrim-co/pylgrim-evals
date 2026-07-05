-- Append-only migrations (CLAUDE.md rule 5): never edit after merge.
CREATE TABLE customers (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  email text NOT NULL UNIQUE,
  vat_id text
);

CREATE TABLE invoices (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  customer_id uuid NOT NULL REFERENCES customers(id),
  total_cents bigint NOT NULL CHECK (total_cents >= 0),
  currency text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
