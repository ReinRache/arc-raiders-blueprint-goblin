from supabase import Client, create_client

# Safe to embed in client code by design — this is the "publishable" key, not
# a secret. Supabase's security boundary is the RLS policies on the database
# (see supabase/schema.sql), not keeping this key hidden. Confirmed against
# Supabase's own docs before committing to this, unlike the Steam Web API key
# (storage/local_credentials.py), which Valve's docs explicitly forbid
# shipping with a client.
SUPABASE_URL = "https://ysagpirtcslsnbqotwhp.supabase.co"
SUPABASE_PUBLISHABLE_KEY = "sb_publishable_utXtFg0X3RXdbDOZaSs9RA_ZSX8oXGn"


def create_supabase_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY)
