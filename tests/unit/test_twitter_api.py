import json
import unittest
from pathlib import Path
from unittest import mock

import requests
from requests.exceptions import Timeout

from src.twitter_api import (ClientErrorException, DoseNotExistException,
                             LateLimitException, RetryOverException,
                             ServerErrorException, TwitterApi)


def read_json(file: Path) -> dict:
    with file.open("r", encoding="utf-8") as f:
        return json.load(f)


def responce(status_code: int, content_path: Path) -> requests.Response:
    result = requests.Response()
    result.status_code = status_code
    result._content = json.dumps(read_json(content_path)).encode()
    result.encoding = "json"
    return result


def param() -> dict:
    return {
        "tweet.fields": "id",
        "pagination_token": "hogehoge",
    }


def build_test_file_path(file_name: str) -> Path:
    return Path.cwd() / "tests" / "unit" / file_name


class TwitterApiTest(unittest.TestCase):

    def test_init(self):
        # 認証周り
        # ヘッダーは以下がサンプル
        # https://github.com/twitterdev/Twitter-API-v2-sample-code/blob/main/Tweet-Lookup/get_tweets_with_bearer_token.py#L26
        # テストの実行
        api = TwitterApi("sample")
        # アサーション
        self.assertEqual(api.bearer_token, "sample")
        self.assertTrue("Authorization" in api.header.keys())
        self.assertEqual(api.header["Authorization"], "Bearer sample")

    def test_responce_200(self):
        # 初期化
        api = TwitterApi("sample")
        res = responce(200, build_test_file_path("statuses_show_ok.json"))
        # テストの実行
        ret = api._responce(res, param())
        # アサーション
        self.assertEqual(ret["id_str"], "1499999999999999999")

    def test_responce_404(self):
        self._responce_test(404, DoseNotExistException)

    def test_responce_5xx(self):
        for status in [500, 502, 503, 504]:
            self._responce_test(status, ServerErrorException)

    def test_responce_429(self):
        self._responce_test(429, LateLimitException)

    def test_responce_others(self):
        for status in [400, 401, 402, 403, 405, 406, 407, 408, 409, 410, 411,
                       412, 413, 414, 415, 416, 417, 418, 421, 422, 423, 424, 425, 426, 428, 431, 451]:
            self._responce_test(status, ClientErrorException)

    def test_responce_json_decord_error(self):
        # 初期化
        res = requests.Response()
        res.status_code = 400
        res._content = "sample".encode()
        res.encoding = "json"
        api = TwitterApi("sample")
        # テストの実行
        with self.assertRaises(ClientErrorException) as e:
            api._responce(res, param())
        # アサーション
        self.assertIn('"JSONDecodeError"', str(e.exception))
        self.assertIn('"Response": "sample"', str(e.exception))
        self.assertIn('"pagination_token": "hogehoge"', str(e.exception))

    @mock.patch("requests.get")
    def test_get_liked_tweets(self, request_get_mock: mock.Mock):
        # 初期化
        api = TwitterApi("sample")
        request_get_mock.return_value = responce(
            200, build_test_file_path("get_liked_tweets_ok.json"))
        # テストの実行
        res = api.get_liked_tweets("sample")
        # アサーション
        self.assertDictEqual(res, read_json(
            build_test_file_path("get_liked_tweets_ok.json")))

    @mock.patch("requests.get")
    @mock.patch("time.sleep")
    def test_get_liked_tweets_retry(self, time_sleep_mock: mock.Mock, request_get_mock: mock.Mock):
        # 初期化
        api = TwitterApi("sample")
        request_get_mock.side_effect = [
            responce(500, build_test_file_path("get_liked_tweets_error.json")),
            Timeout(),
            responce(200, build_test_file_path("get_liked_tweets_ok.json")),
        ]
        # テストの実行
        res = api.get_liked_tweets("sample")
        # アサーション
        self.assertDictEqual(res, read_json(
            build_test_file_path("get_liked_tweets_ok.json")))
        self.assertEqual(request_get_mock.call_count, 3)
        self.assertEqual(time_sleep_mock.call_count, 2)
        self.assertEqual(time_sleep_mock.call_args_list[0][0][0], 15)
        self.assertEqual(time_sleep_mock.call_args_list[1][0][0], 15)

    @mock.patch("requests.get")
    @mock.patch("time.sleep")
    def test_get_liked_tweets_retry_over(self, time_sleep_mock: mock.Mock, request_get_mock: mock.Mock):
        # 初期化
        api = TwitterApi("sample")
        request_get_mock.side_effect = [
            responce(500, build_test_file_path("get_liked_tweets_error.json")),
            responce(500, build_test_file_path("get_liked_tweets_error.json")),
            responce(500, build_test_file_path("get_liked_tweets_error.json")),
        ]
        # テストの実行
        with self.assertRaises(RetryOverException) as e:
            api.get_liked_tweets("sample")
        # アサーション
        self.assertEqual(e.exception.status_code, 400)
        self.assertIn('"0": {"errors"', str(e.exception))
        self.assertIn('"1": {"errors"', str(e.exception))
        self.assertIn('"2": {"errors"', str(e.exception))
        self.assertIn("Retry Limit. 3", str(e.exception))
        self.assertEqual(request_get_mock.call_count, 3)
        self.assertEqual(time_sleep_mock.call_count, 3)
        for args in time_sleep_mock.call_args_list:
            self.assertEqual(args[0][0], 15)

    @mock.patch("requests.get")
    def test_get_statuses_show_ok(self, request_get_mock: mock.Mock):
        # 初期化
        api = TwitterApi("sample")
        request_get_mock.return_value = responce(
            200, build_test_file_path("statuses_show_ok.json"))
        # テストの実行
        res = api.get_statuses_show("sample")
        # アサーション
        self.assertDictEqual(res, read_json(
            build_test_file_path("statuses_show_ok.json")))

    @mock.patch("requests.get")
    @mock.patch("time.sleep")
    def test_get_statuses_show_retry(self, time_sleep_mock: mock.Mock, request_get_mock: mock.Mock):
        # 初期化
        api = TwitterApi("sample")
        request_get_mock.side_effect = [
            responce(500, build_test_file_path("statuses_show_error.json")),
            Timeout(),
            responce(200, build_test_file_path("statuses_show_ok.json")),
        ]
        # テストの実行
        res = api.get_statuses_show("sample")
        # アサーション
        self.assertDictEqual(res, read_json(
            build_test_file_path("statuses_show_ok.json")))
        self.assertEqual(request_get_mock.call_count, 3)
        self.assertEqual(time_sleep_mock.call_count, 2)
        self.assertEqual(time_sleep_mock.call_args_list[0][0][0], 15)
        self.assertEqual(time_sleep_mock.call_args_list[1][0][0], 15)

    @mock.patch("requests.get")
    @mock.patch("time.sleep")
    def test_get_statuses_show_retry_over(self, time_sleep_mock: mock.Mock, request_get_mock: mock.Mock):
        # 初期化
        api = TwitterApi("sample")
        request_get_mock.side_effect = [
            responce(500, build_test_file_path("statuses_show_error.json")),
            responce(500, build_test_file_path("statuses_show_error.json")),
            responce(500, build_test_file_path("statuses_show_error.json")),
        ]
        # テストの実行
        with self.assertRaises(RetryOverException) as e:
            api.get_statuses_show("sample")
        # アサーション
        self.assertEqual(e.exception.status_code, 400)
        self.assertIn('"0": {"errors"', str(e.exception))
        self.assertIn('"1": {"errors"', str(e.exception))
        self.assertIn('"2": {"errors"', str(e.exception))
        self.assertIn("Retry Limit. 3", str(e.exception))
        self.assertEqual(request_get_mock.call_count, 3)
        self.assertEqual(time_sleep_mock.call_count, 3)
        for args in time_sleep_mock.call_args_list:
            self.assertEqual(args[0][0], 15)

    @mock.patch("requests.get")
    @mock.patch("time.sleep")
    def test_get_statuses_show_retry_429(self, time_sleep_mock: mock.Mock, request_get_mock: mock.Mock):
        # 初期化
        api = TwitterApi("sample")
        request_get_mock.side_effect = [
            responce(429, build_test_file_path("statuses_show_error.json")),
            responce(200, build_test_file_path("statuses_show_ok.json")),
        ]
        # テストの実行
        res = api.get_statuses_show("sample")
        # アサーション
        self.assertDictEqual(res, read_json(
            build_test_file_path("statuses_show_ok.json")))
        self.assertEqual(request_get_mock.call_count, 2)
        self.assertEqual(time_sleep_mock.call_count, 1)
        self.assertEqual(time_sleep_mock.call_args[0][0], 900)

    @mock.patch("requests.get")
    @mock.patch("time.sleep")
    def test_get_statuses_show_not_retry(self, time_sleep_mock: mock.Mock, request_get_mock: mock.Mock):
        # 初期化
        api = TwitterApi("sample")
        request_get_mock.side_effect = [
            responce(400, build_test_file_path("statuses_show_error.json")),
        ]
        # テストの実行
        with self.assertRaises(ClientErrorException) as e:
            api.get_statuses_show("sample")
        # アサーション
        self.assertEqual(e.exception.status_code, 400)
        self.assertEqual(time_sleep_mock.call_count, 0)

    def _responce_test(self, status_code: int, exception: Exception):
        # 初期化
        api = TwitterApi("sample")
        res = responce(status_code, build_test_file_path(
            "statuses_show_error.json"))
        # テストの実行
        with self.assertRaises(exception) as e:
            api._responce(res, param())
        # アサーション
        self.assertIn('"pagination_token": "hogehoge"', str(e.exception))


if __name__ == "__main__":
    unittest.main()
