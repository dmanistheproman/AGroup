"""<<control>> LoginController — Log In use case (X-03), suspended accounts (UA01-T04)."""


class AuthenticationError(Exception):
    """Not logged in, or wrong email/password (HTTP 401)."""


class LoginController:
    SESSION_KEY = "user_id"

    def __init__(self, account_repo, session_provider):
        # session_provider() returns the current session mapping (flask.session in the app,
        # a plain dict in tests), so this class does not depend on Flask.
        self.accounts = account_repo
        self.session = session_provider

    def login(self, email, password):
        email = (email or "").strip()
        if not email or not password:
            raise ValueError("Enter your email and password.")
        account = self.accounts.find_by_email(email)
        if account is None or not account.verify_password(password):
            # Same message for both cases, so the form does not reveal which emails exist.
            raise AuthenticationError("Incorrect email or password.")
        if not account.is_active():
            raise PermissionError("This account is suspended. Contact support for help.")
        self._start_session(account.id)
        return account

    def logout(self):
        self.session().pop(self.SESSION_KEY, None)

    def current_user(self):
        """The logged-in UserAccount, or None. Ends the session of a suspended or removed account."""
        session = self.session()
        user_id = session.get(self.SESSION_KEY)
        if user_id is None:
            return None
        account = self.accounts.get(user_id)
        if account is None or not account.is_active():
            session.pop(self.SESSION_KEY, None)
            return None
        return account

    def _start_session(self, user_id):
        session = self.session()
        session.pop(self.SESSION_KEY, None)
        session[self.SESSION_KEY] = user_id
