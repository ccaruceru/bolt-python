import json
from time import time
from urllib.parse import quote

from slack_sdk.signature import SignatureVerifier
from slack_sdk.web import WebClient

from slack_bolt.app import App
from slack_bolt.request import BoltRequest
from tests.mock_web_api_server import (
    setup_mock_web_api_server,
    cleanup_mock_web_api_server,
)
from tests.utils import remove_os_env_temporarily, restore_os_env


class TestMiddleware:
    signing_secret = "secret"
    valid_token = "xoxb-valid"
    mock_api_server_base_url = "http://localhost:8888"
    signature_verifier = SignatureVerifier(signing_secret)
    web_client = WebClient(token=valid_token, base_url=mock_api_server_base_url,)

    def setup_method(self):
        self.old_os_env = remove_os_env_temporarily()
        setup_mock_web_api_server(self)

    def teardown_method(self):
        cleanup_mock_web_api_server(self)
        restore_os_env(self.old_os_env)

    def build_request(self) -> BoltRequest:
        payload = {
            "type": "shortcut",
            "token": "verification_token",
            "action_ts": "111.111",
            "team": {
                "id": "T111",
                "domain": "workspace-domain",
                "enterprise_id": "E111",
                "enterprise_name": "Org Name",
            },
            "user": {"id": "W111", "username": "primary-owner", "team_id": "T111"},
            "callback_id": "test-shortcut",
            "trigger_id": "111.111.xxxxxx",
        }
        timestamp, body = str(int(time())), json.dumps(payload)
        return BoltRequest(
            body=body,
            headers={
                "content-type": ["application/json"],
                "x-slack-signature": [
                    self.signature_verifier.generate_signature(
                        body=body, timestamp=timestamp,
                    )
                ],
                "x-slack-request-timestamp": [timestamp],
            },
        )

    def test_no_next_call(self):
        app = App(client=self.web_client, signing_secret=self.signing_secret,)
        app.use(no_next)
        app.shortcut("test-shortcut")(just_ack)

        response = app.dispatch(self.build_request())
        assert response.status == 404
        assert self.mock_received_requests["/auth.test"] == 1

    def test_next_call(self):
        app = App(client=self.web_client, signing_secret=self.signing_secret,)
        app.use(just_next)
        app.shortcut("test-shortcut")(just_ack)

        response = app.dispatch(self.build_request())
        assert response.status == 200
        assert response.body == "acknowledged!"
        assert self.mock_received_requests["/auth.test"] == 1


def just_ack(ack):
    ack("acknowledged!")


def no_next():
    pass


def just_next(next):
    next()
