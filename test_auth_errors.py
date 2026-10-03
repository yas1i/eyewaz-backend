"""Sign-in failures on protected endpoints answer 401 with a readable message,
never a 500 (Flask-RESTful used to swallow flask_jwt_extended's errors)."""
import unittest

from flask_jwt_extended import create_access_token

from server import app


class AuthErrorTests(unittest.TestCase):
    def setUp(self):
        self.c = app.test_client()

    def _check_401(self, method, path, headers=None):
        r = getattr(self.c, method)(path, headers=headers or {})
        self.assertEqual(r.status_code, 401, f"{method.upper()} {path}: {r.status_code}")
        self.assertEqual(r.get_json(), {"message": "Please sign in again."})

    def test_missing_token(self):
        for method, path in (("get", "/api/dialects"), ("post", "/api/speak"),
                             ("post", "/api/translate")):
            self._check_401(method, path)

    def test_malformed_token(self):
        self._check_401("get", "/api/dialects", {"Authorization": "Bearer a.b.c"})

    def test_wrong_signature(self):
        forged = ("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
                  "eyJzdWIiOiJ4QHkueiIsImZyZXNoIjpmYWxzZSwidHlwZSI6ImFjY2VzcyJ9."
                  "c2lnbmF0dXJlLW5vdC12YWxpZA")
        self._check_401("get", "/api/dialects", {"Authorization": "Bearer " + forged})

    def test_valid_token_still_works(self):
        with app.app_context():
            tok = create_access_token(identity="auth-test@example.com")
        r = self.c.get("/api/dialects", headers={"Authorization": "Bearer " + tok})
        self.assertEqual(r.status_code, 200)
        self.assertIn("dialects", r.get_json())

    def test_other_errors_still_json_500_or_404(self):
        r = self.c.get("/api/does-not-exist")
        self.assertEqual(r.status_code, 404)


if __name__ == "__main__":
    unittest.main()
