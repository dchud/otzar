"""Login throttling with django-axes."""

import pytest
from django.contrib.auth.models import User
from django.test import Client


@pytest.fixture
def users(db):
    User.objects.create_user(username="alice", password="right-password")
    User.objects.create_user(username="bob", password="bobs-password")


def _attempt(client, username, password):
    return client.post(
        "/accounts/login/",
        {"username": username, "password": password},
        REMOTE_ADDR="198.51.100.7",
    )


def _fail(client, username, times):
    return [
        _attempt(client, username, "wrong").status_code for _ in range(times)
    ]


def test_fifth_failure_locks_the_username_at_that_address(users):
    client = Client()
    assert _fail(client, "alice", 4) == [200] * 4

    response = _attempt(client, "alice", "wrong")

    assert response.status_code == 429
    assert "Too many attempts" in response.content.decode()


def test_locked_username_is_refused_even_with_the_right_password(users):
    client = Client()
    _fail(client, "alice", 5)

    response = _attempt(client, "alice", "right-password")

    assert response.status_code == 429
    assert "_auth_user_id" not in client.session


def test_lockout_does_not_extend_to_another_username(users):
    client = Client()
    _fail(client, "alice", 5)

    response = _attempt(client, "bob", "bobs-password")

    assert response.status_code == 302
    assert client.session["_auth_user_id"]


def test_lockout_page_does_not_name_the_username(users):
    client = Client()
    _fail(client, "alice", 5)

    response = _attempt(client, "alice", "wrong")

    assert "alice" not in response.content.decode()


def test_success_clears_the_failure_count(users):
    client = Client()
    _fail(client, "alice", 4)
    assert _attempt(client, "alice", "right-password").status_code == 302

    client.logout()
    _fail(client, "alice", 4)

    assert _attempt(client, "alice", "right-password").status_code == 302


def test_admin_login_is_throttled_too(users):
    client = Client()
    for _ in range(5):
        response = client.post(
            "/admin/login/",
            {"username": "alice", "password": "wrong"},
            REMOTE_ADDR="198.51.100.7",
        )

    assert response.status_code == 429


def test_logins_leave_no_access_log(users):
    from axes.models import AccessAttempt, AccessLog

    client = Client()
    _fail(client, "alice", 1)
    assert _attempt(client, "alice", "right-password").status_code == 302

    assert AccessLog.objects.count() == 0
    # The success cleared the failure it followed.
    assert AccessAttempt.objects.count() == 0
