import http.client
import json
import unittest
from bridge import StatusBridge


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.state = {"app": "FocusHarbor", "version": 1, "youtubePrompt": True}
        self.bridge = StatusBridge(lambda: self.state, port=0)
        self.port = self.bridge.server.server_port

    def tearDown(self):
        self.bridge.close()

    def request(self, path="/status", method="GET", headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=2)
        connection.request(method, path, headers=headers or {})
        response = connection.getresponse()
        result = response.status, response.read()
        connection.close()
        return result

    def test_status_tracks_policy(self):
        code, body = self.request()
        self.assertEqual(code, 200)
        self.assertTrue(json.loads(body)["youtubePrompt"])
        self.state["youtubePrompt"] = False
        self.assertFalse(json.loads(self.request()[1])["youtubePrompt"])

    def test_no_write_endpoint_or_arbitrary_host(self):
        self.assertEqual(self.request(method="POST")[0], 501)
        self.assertEqual(self.request(path="/unblock")[0], 404)
        self.assertEqual(self.request(headers={"Host": "evil.example"})[0], 403)


if __name__ == "__main__":
    unittest.main()
