-- Create a separate test database so pytest never destroys dev data.
-- This runs only on first init (empty data volume).
CREATE DATABASE noa_test OWNER noa;
