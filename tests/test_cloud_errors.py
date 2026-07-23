from arc_companion.cloud.errors import describe_error


def test_describe_error_uses_message_and_code_when_both_present():
    class FakeApiError(Exception):
        message = "new row violates row-level security policy"
        code = "42501"

    assert describe_error(FakeApiError()) == "FakeApiError: new row violates row-level security policy [42501]"


def test_describe_error_uses_message_alone_without_code():
    class FakeAuthError(Exception):
        message = "Auth session missing!"
        code = None

    assert describe_error(FakeAuthError()) == "FakeAuthError: Auth session missing!"


def test_describe_error_falls_back_to_class_name_without_message():
    assert describe_error(ConnectionError("boom")) == "ConnectionError"


def test_describe_error_falls_back_to_class_name_when_message_is_empty_string():
    class FakeError(Exception):
        message = ""
        code = "some_code"

    assert describe_error(FakeError()) == "FakeError"


def test_describe_error_matches_real_postgrest_api_error():
    from postgrest.exceptions import APIError

    exc = APIError(
        {
            "message": "duplicate key value violates unique constraint \"profiles_arbg_user_id_key\"",
            "code": "23505",
            "hint": None,
            "details": None,
        }
    )
    assert describe_error(exc) == (
        'APIError: duplicate key value violates unique constraint "profiles_arbg_user_id_key" [23505]'
    )


def test_describe_error_matches_real_supabase_auth_error():
    from supabase_auth.errors import AuthApiError

    exc = AuthApiError("Invalid Refresh Token: Already Used", 401, "bad_jwt")
    assert describe_error(exc) == "AuthApiError: Invalid Refresh Token: Already Used [bad_jwt]"
