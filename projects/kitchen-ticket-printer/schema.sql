-- Queue table the order workflow writes to and the printer service reads from.
CREATE TABLE tickets_impresion (
  id               SERIAL PRIMARY KEY,
  folio            TEXT NOT NULL,
  cliente_nombre   TEXT,
  cliente_telefono TEXT,
  pedido_json      TEXT NOT NULL,          -- [{"cantidad":2,"producto":"...","tamano":"..."}]
  total            NUMERIC,
  forma_pago       TEXT,
  tipo_entrega     TEXT,                   -- 'recoger' | 'domicilio'
  direccion        TEXT,
  impreso          BOOLEAN NOT NULL DEFAULT FALSE,
  creado_en        TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_tickets_pending ON tickets_impresion (id) WHERE impreso = FALSE;
