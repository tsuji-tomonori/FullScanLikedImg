import json
import time

import requests
from requests.exceptions import Timeout, JSONDecodeError


def retry(func):
    def wrapper(*args, **kwargs):
        max_retry_count = 3
        error = {}
        for idx in range(max_retry_count):
            try:
                return func(*args, **kwargs)
            except ServerErrorException as se:
                # リトライ実施
                time.sleep(15)
                error[idx] = se.error
            except Timeout:
                # リトライ実施
                time.sleep(15)
                error[idx] = "Time out error"
            except LateLimitException as le:
                # リトライ実施
                time.sleep(900)
                error[idx] = le.error
            except Exception as e:
                # 上記以外の例外はそのまま投げる
                raise e
        # リトライしつくしても失敗した場合
        error["message"] = f"Retry Limit. {max_retry_count}"
        raise RetryOverException(400, error)
    return wrapper


class TwitterApi:
    def __init__(self, bearer_token: str) -> None:
        self.bearer_token = bearer_token
        self.header = self._build_header()

    def _build_header(self) -> dict:
        return {
            "Authorization": f"Bearer {self.bearer_token}"
        }

    def _responce(self, res: requests.Response, params: dict) -> dict:
        # https://developer.twitter.com/en/support/twitter-api/error-troubleshooting
        if res.status_code in [200, 304]:
            return res.json()
        try:
            error = res.json() | params
        except JSONDecodeError as e:
            error = params
            error["JSONDecodeError"] = str(e)
            error["Response"] = str(res.text)
        if res.status_code in [404]:
            raise DoseNotExistException(res.status_code, error)
        if res.status_code in [500, 502, 503, 504]:
            raise ServerErrorException(res.status_code, error)
        if res.status_code in [429]:
            raise LateLimitException(res.status_code, error)
        # その他400系のエラーのみが残る想定
        raise ClientErrorException(res.status_code, error)

    def _requests_get(self, url: str, params: dict, timeout: int = 10) -> dict:
        return self._responce(requests.get(url, headers=self.header, params=params, timeout=timeout), params)

    @ retry
    def get_liked_tweets(self, id: str, next_token: str = None) -> list:
        params = {
            "tweet.fields": "id",
        }
        if next_token:
            params["pagination_token"] = next_token
        url = f"https://api.twitter.com/2/users/{id}/liked_tweets"
        return self._requests_get(url, params)

    @ retry
    def get_statuses_show(self, id: str) -> dict:
        params = {
            "id": id,
        }
        url = "https://api.twitter.com/1.1/statuses/show.json"
        return self._requests_get(url, params)


class TwitterException(Exception):
    def __init__(self, status_code: str, error: dict, *args: object) -> None:
        super().__init__(*args)
        self.status_code = status_code
        self.error = error

    def __str__(self) -> str:
        return f"[{self.status_code}] {json.dumps(self.error)}"


class ServerErrorException(TwitterException):
    def __init__(self, status_code: str, error: dict, *args: object) -> None:
        super().__init__(status_code, error, *args)


class ClientErrorException(TwitterException):
    def __init__(self, status_code: str, error: dict, *args: object) -> None:
        super().__init__(status_code, error, *args)


class RetryOverException(TwitterException):
    def __init__(self, status_code: str, error: dict, *args: object) -> None:
        super().__init__(status_code, error, *args)


class DoseNotExistException(TwitterException):
    def __init__(self, status_code: str, error: dict, *args: object) -> None:
        super().__init__(status_code, error, *args)


class LateLimitException(TwitterException):
    def __init__(self, status_code: str, error: dict, *args: object) -> None:
        super().__init__(status_code, error, *args)
