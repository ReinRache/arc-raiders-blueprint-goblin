def describe_error(exc: Exception) -> str:
    """Short, specific label for a caught exception, for surfacing in the UI
    instead of a bare "check your connection" with no further detail.
    postgrest.exceptions.APIError and every supabase_auth.errors.AuthError
    subclass carry a real .message (and often .code) describing what
    Supabase's API actually rejected -- an RLS violation, a unique
    constraint violation, a bad request -- which is far more useful than the
    exception's class name alone. Duck-typed (getattr, not an isinstance
    check against either library) so it also degrades gracefully for
    anything else, e.g. a plain httpx connection error, where the class name
    alone (ConnectError, ConnectTimeout, ...) is already fairly
    self-descriptive."""
    message = getattr(exc, "message", None)
    code = getattr(exc, "code", None)
    if not message:
        return type(exc).__name__
    if code:
        return f"{type(exc).__name__}: {message} [{code}]"
    return f"{type(exc).__name__}: {message}"
