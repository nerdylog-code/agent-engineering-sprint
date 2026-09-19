import unittest
from datetime import UTC, datetime, timedelta

import jwt

from agent_lab.auth import AuthenticationError, JWTAuthenticator


class JWTAuthTests(unittest.TestCase):
    def setUp(self):
        self.secret = "test-secret-0123456789-0123456789"
        self.auth = JWTAuthenticator(secret=self.secret, issuer="issuer", audience="audience")

    def test_valid_claims_decode_to_principal(self):
        token = self.auth.issue(subject="alice", tenant_id="tenant-a", roles=["user"], scopes=["tools:calculator"])
        principal = self.auth.decode(token)
        self.assertEqual(principal.subject, "alice")
        self.assertEqual(principal.tenant_id, "tenant-a")
        self.assertTrue(principal.has_scope("tools:calculator"))
        self.assertFalse(principal.has_scope("tools:admin"))
        self.assertTrue(principal.has_role("user"))
        self.assertFalse(principal.has_role("admin"))

    def test_expired_issuer_audience_and_signature_are_rejected(self):
        expired = jwt.encode(
            {
                "sub": "alice",
                "tenant_id": "tenant-a",
                "roles": [],
                "scopes": [],
                "iss": "issuer",
                "aud": "audience",
                "iat": datetime.now(UTC) - timedelta(hours=2),
                "exp": datetime.now(UTC) - timedelta(hours=1),
            },
            self.secret,
            algorithm="HS256",
        )
        for token in (
            expired,
            jwt.encode(
                {
                    "sub": "alice", "tenant_id": "tenant-a", "roles": [], "scopes": [],
                    "iss": "issuer", "aud": "audience", "iat": datetime.now(UTC),
                    "exp": datetime.now(UTC) + timedelta(minutes=5),
                },
                "wrong-secret-0123456789-0123456789",
                algorithm="HS256",
            ),
        ):
            with self.assertRaises(AuthenticationError):
                self.auth.decode(token)
        wrong_aud = jwt.encode(
            {
                "sub": "alice", "tenant_id": "tenant-a", "roles": [], "scopes": [],
                "iss": "issuer", "aud": "wrong", "iat": datetime.now(UTC),
                "exp": datetime.now(UTC) + timedelta(minutes=5),
            },
            self.secret, algorithm="HS256",
        )
        with self.assertRaises(AuthenticationError):
            self.auth.decode(wrong_aud)
        wrong_issuer = jwt.encode(
            {
                "sub": "alice", "tenant_id": "tenant-a", "roles": [], "scopes": [],
                "iss": "wrong", "aud": "audience", "iat": datetime.now(UTC),
                "exp": datetime.now(UTC) + timedelta(minutes=5),
            },
            self.secret, algorithm="HS256",
        )
        with self.assertRaises(AuthenticationError):
            self.auth.decode(wrong_issuer)

    def test_signing_algorithm_must_be_allowlisted(self):
        with self.assertRaises(ValueError):
            self.auth.issue(subject="alice", tenant_id="tenant-a", algorithm="HS512")


if __name__ == "__main__":
    unittest.main()
