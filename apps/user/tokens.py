from datetime import date
from django.conf import settings
from django.utils.http import int_to_base36, base36_to_int
from django.utils.crypto import constant_time_compare, salted_hmac
import base64

class EmailConfirmationTokenGenerator(object):
    """
    Strategy object used to generate and check tokens for the email
    confirmation mechanism.
    """
    def make_token(self, user):
        """
        Returns a token that can be used once to do a email confirmation
        for the given user.
        """
        return self._make_token_with_timestamp(user, self._num_days(self._today()))

    def check_token(self, user, token):
        """
        Check that a email confirmation token is correct for a given user.
        """
        # Parse the token
        try:
            ts_b36, hash = token.split("-")
        except (ValueError, AttributeError):
            return False

        try:
            ts = base36_to_int(ts_b36)
        except ValueError:
            return False

        # Check that the timestamp/uid has not been tampered with
        if not constant_time_compare(self._make_token_with_timestamp(user, ts), token):
            return False

        # Check the timestamp is within limit
        #if (self._num_days(self._today()) - ts) > settings.EMAIL_CONFIRMATION_TIMEOUT_DAYS:
        #    return False

        return True

    def _make_token_with_timestamp(self, user, timestamp):
        # timestamp is number of days since 2001-1-1.  Converted to
        # base 36, this gives us a 3 digit string until about 2121
        ts_b36 = int_to_base36(timestamp)

        # By hashing on the internal state of the user and using state
        # that is sure to change (the email salt will change since
        # the email address was changed, and
        # last_login will also change), we produce a hash that will be
        # invalid as soon as it is used.
        # We limit the hash to 20 chars to keep URL short
        key_salt = "apps.user.tokens.EmailConfirmationTokenGenerator"

        # Ensure results are consistent across DB backends
        login_timestamp = user.last_login.replace(microsecond=0, tzinfo=None)

        value = (unicode(user.id) + user.email +
                unicode(login_timestamp) + unicode(timestamp))
        hash = salted_hmac(key_salt, value).hexdigest()[::2]
        return "%s-%s" % (ts_b36, hash)

    def _num_days(self, dt):
        return (dt - date(2001, 1, 1)).days

    def _today(self):
        # Used for mocking in tests
        return date.today()

class APIRegistrationTokenGenerator(object):
    """
    Strategy object used to generate and check tokens for the API sign up process
    """
    valid_issuers = ['purse', 'shopify', 'amazon']

    def make_token(self, user):
        """
        Returns a token that can be used once to do a email confirmation
        for the given user.
        """
        return self._make_token_with_timestamp(user, self._num_days(self._today()))

    def check_token(self, user, token, encoded_issuer):
        """
        Check that a email confirmation token is correct for a given user.
        """
        # Parse the token
        try:
            ts_b36, hash = token.split("-")
        except (ValueError, AttributeError):
            return False

        try:
            ts = base36_to_int(ts_b36)
        except ValueError:
            return False

        # Check that the timestamp/uid has not been tampered with
        if not constant_time_compare(self._make_token_with_timestamp(user, ts), token):
            return False

        # Check the timestamp is within limit
        #if (self._num_days(self._today()) - ts) > settings.API_REGISTRATION_TIMEOUT_DAYS:
        #    return False

        issuer = base64.b64decode(encoded_issuer) if encoded_issuer else None
        if issuer not in self.valid_issuers:
            return False

        return True

    def _make_token_with_timestamp(self, user, timestamp):
        # timestamp is number of days since 2001-1-1.  Converted to
        # base 36, this gives us a 3 digit string until about 2121
        ts_b36 = int_to_base36(timestamp)

        # By hashing on the internal state of the user and using state
        # that is sure to change (the email salt will change since
        # the email address was changed, and
        # last_login will also change), we produce a hash that will be
        # invalid as soon as it is used.
        # We limit the hash to 20 chars to keep URL short
        key_salt = "apps.user.tokens.APIRegistrationTokenGenerator"

        # Ensure results are consistent across DB backends
        login_timestamp = user.last_login.replace(microsecond=0, tzinfo=None)

        value = (unicode(user.id) + user.email +
                unicode(login_timestamp) + unicode(timestamp))
        hash = salted_hmac(key_salt, value).hexdigest()[::2]
        return "%s-%s" % (ts_b36, hash)

    def _num_days(self, dt):
        return (dt - date(2001, 1, 1)).days

    def _today(self):
        # Used for mocking in tests
        return date.today()

class ExclusiveClubTokenGenerator(object):
    """
    Strategy object used to generate and check tokens for joining an exclusive club
    """
    valid_clubs = ('purse', )

    def make_token(self, user):
        """
        Returns a token that can be used once to do a email confirmation
        for the given user.
        """
        return self._make_token_with_timestamp(user, self._num_days(self._today()))

    def check_token(self, user, token, encoded_club):
        """
        Check that a email confirmation token is correct for a given user.
        """
        # Parse the token
        try:
            ts_b36, hash = token.split("-")
        except (ValueError, AttributeError):
            return False

        try:
            ts = base36_to_int(ts_b36)
        except ValueError:
            return False

        # Check that the timestamp/uid has not been tampered with
        if not constant_time_compare(self._make_token_with_timestamp(user, ts), token):
            return False

        club = base64.b64decode(encoded_club) if encoded_club else None
        if club not in self.valid_clubs:
            return False

        return True

    def _make_token_with_timestamp(self, user, timestamp):
        # timestamp is number of days since 2001-1-1.  Converted to
        # base 36, this gives us a 3 digit string until about 2121
        ts_b36 = int_to_base36(timestamp)

        # By hashing on the internal state of the user and using state
        # that is sure to change (the email salt will change since
        # the email address was changed, and
        # last_login will also change), we produce a hash that will be
        # invalid as soon as it is used.
        # We limit the hash to 20 chars to keep URL short
        key_salt = "apps.user.tokens.ExclusiveClubTokenGenerator"

        value = (unicode(user.id) + user.email + unicode(timestamp))
        hash = salted_hmac(key_salt, value).hexdigest()[::2]
        return "%s-%s" % (ts_b36, hash)

    def _num_days(self, dt):
        return (dt - date(2001, 1, 1)).days

    def _today(self):
        # Used for mocking in tests
        return date.today()

email_confirmation_token_generator = EmailConfirmationTokenGenerator()
api_registration_token_generator = APIRegistrationTokenGenerator()
exclusive_club_token_generator = ExclusiveClubTokenGenerator()