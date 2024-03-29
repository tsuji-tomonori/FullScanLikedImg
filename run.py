from __future__ import annotations

import datetime
import os
import socket
import time
from pathlib import Path
from typing import NamedTuple
from urllib.error import HTTPError
from urllib.request import urlopen

import boto3

from src.twitter_api import DoseNotExistException, TwitterApi


class EnvironParamaters(NamedTuple):
    # 環境変数
    BEARER_TOKEN: str
    LIKED_USER_ID: str
    PROPERTY_DB_NAME: str
    PAGE_TOKE_DB_NAME: str
    OUTPUT_DIR: str
    PAGETOKE_RESET: bool


class AwsResource():

    def __init__(self, env_param: EnvironParamaters, session: boto3.Session = None) -> None:
        self.env_param = env_param
        if session is None:
            session = boto3.Session()
        self.ssm_client = session.client("ssm")
        dynamodb = session.resource('dynamodb')
        self.property_table = dynamodb.Table(self.env_param.PROPERTY_DB_NAME)
        self.pagetoken_table = dynamodb.Table(self.env_param.PAGE_TOKE_DB_NAME)

    def get_value_from_ssm(self, key: str) -> str:
        value = self.ssm_client.get_parameter(
            Name=key,
            WithDecryption=True
        )
        return value["Parameter"]["Value"]

    def put_property(self, item: dict) -> None:
        self.property_table.put_item(
            Item=item
        )

    def has_property_item(self, key: str) -> bool:
        res = self.property_table.get_item(
            Key={
                "partition_key": key
            }
        )
        return bool(res.get("Item"))

    def get_pagetoken(self) -> str:
        value = self.pagetoken_table.get_item(
            Key={
                "liked_user_id": self.env_param.LIKED_USER_ID
            }
        )
        return value["Item"]["page_token"]

    def put_pagetoken(self, pagetoken: str) -> None:
        self.pagetoken_table.put_item(
            Item={
                "liked_user_id": self.env_param.LIKED_USER_ID,
                "page_token": pagetoken,
                "timestamp": now_isof(),
            }
        )


def to_jst_timezone(timestr: str, format: str) -> datetime.datetime:
    tt = datetime.datetime.strptime(timestr, format)
    jst_delta = datetime.timedelta(hours=9)
    jst_zone = datetime.timezone(jst_delta)
    tt += jst_delta
    return tt.astimezone(jst_zone)


def twitter_to_jst_timezone(timestr: str) -> datetime.datetime:
    return to_jst_timezone(timestr, "%a %b %d %H:%M:%S +0000 %Y")


def now_isof() -> str:
    now = datetime.datetime.now(datetime.timezone.utc)
    jst_zone = datetime.timezone(datetime.timedelta(hours=9))
    result = now.astimezone(jst_zone).isoformat()
    return result


def write_img(path: Path, data: bin) -> str:
    with path.open("wb") as f:
        f.write(data)
    return now_isof()


def download_img(url: str) -> bin | None:
    exception = None
    wait_time = 30
    for _ in range(10):
        try:
            with urlopen(rebuild_url(url), timeout=20.0) as twitter_img:
                return twitter_img.read()
        except HTTPError as e:
            if e.code in [504, 500]:
                # リトライ実施
                exception = e
                print(f"start retry wait {wait_time}...")
                time.sleep(wait_time)
                wait_time *= 2
            elif e.code in [429]:
                # 固定で300秒まつ
                exception = e
                print(f"start retry wait {wait_time}...")
                time.sleep(wait_time)
                wait_time += 300
            elif e.code == 404:
                return None
            else:
                raise e

        except socket.timeout as te:
            exception = te
            print(f"start retry wait {wait_time}...")
            time.sleep(wait_time)
            wait_time *= 2
    # リトライオーバー
    print("Retry Limit.")
    raise exception


def rebuild_url(before_url: str) -> str:
    # https://pbs.twimg.com/media/hogehoge.jpg
    # https://pbs.twimg.com/media/hogehoge?format=png&name=large
    # に変更することで, 大きなpng画像を取得することが出来る
    return f"{before_url[:-4]}?format=png&name=large"


def make_output_path(output_dir: Path, created_at: datetime.datetime, id: str, index: int) -> Path:
    result = output_dir
    result.mkdir(exist_ok=True)
    result /= f"yyyy={created_at.year}"
    result.mkdir(exist_ok=True)
    result /= f"mm={str(created_at.month).zfill(2)}"
    result.mkdir(exist_ok=True)
    result /= f"dd={str(created_at.day).zfill(2)}"
    result.mkdir(exist_ok=True)
    result /= f"{build_file_name_stem(id, index)}.png"
    return result


def build_file_name_stem(id: str, index: int) -> str:
    return f"{id}_{index}"


def hashtags_to_str(hashtags: list) -> str:
    return ",".join(hashtag["text"] for hashtag in hashtags)


class Action():

    def __init__(self, env_param: EnvironParamaters, output_dir: Path, session: boto3.Session = None) -> None:
        self._env_param = env_param
        self._output_dir = output_dir
        self._aws_resource = AwsResource(env_param, session)

    def __call__(self) -> None:
        print(
            f"service start! target liked user id is {self._env_param.LIKED_USER_ID}")
        print(f"start at: {now_isof()}")
        try:
            self._service()
        except Exception as e:
            print(f"An Error occurrence at: {now_isof()}")
            raise e
        print(f"end at: {now_isof()}")

    def _service(self) -> None:

        bearer_token = self._aws_resource.get_value_from_ssm(
            self._env_param.BEARER_TOKEN)
        api = TwitterApi(bearer_token=bearer_token)
        page_token = None
        if not self._env_param.PAGETOKE_RESET:
            page_token = self._aws_resource.get_pagetoken()

        while True:
            print(f"start get liked tweets at {page_token}")
            ids = api.get_liked_tweets(
                self._env_param.LIKED_USER_ID, page_token)
            is_fin = True
            # いいねが取得できなかった場合, 処理終了
            if len(ids.get("data", [])) == 0:
                return
            for data in ids["data"]:
                try:
                    tweet_info = api.get_statuses_show(data["id"])
                except DoseNotExistException:
                    # 詳細情報が取得できなかった場合skip
                    continue
                if "extended_entities" not in tweet_info.keys():
                    continue
                if "media" not in tweet_info["extended_entities"].keys():
                    continue
                try:
                    is_skip = self._downdload_and_write_db(
                        tweet_info, self._output_dir)
                    if not is_skip:
                        is_fin = False
                except Exception as e:
                    # Twitter API 周り以外で例外が発生した場合
                    # 先にpage_tokenを表示させる
                    print(f"Current page token is: {page_token}")
                    self._aws_resource.put_pagetoken(page_token)
                    raise e
            page_token = ids["meta"]["next_token"]
            self._aws_resource.put_pagetoken(page_token)
            if is_fin:
                return

    def _downdload_and_write_db(self, tweet_info: dict, output_dir: Path) -> None:
        id = tweet_info["id_str"]
        text = tweet_info["text"]
        user_name = tweet_info["user"]["name"]
        user_screen_name = tweet_info["user"]["screen_name"]
        hashtag = hashtags_to_str(tweet_info["entities"]["hashtags"])
        created_at = twitter_to_jst_timezone(tweet_info["created_at"])
        is_skip = True
        # 1ツイート内で投稿されているメディア分ループ
        for idx, extended_entity in enumerate(tweet_info["extended_entities"]["media"]):
            # 投稿されたメディアが画像でない場合, 次のメディアへ
            if extended_entity["type"] != "photo":
                continue
            output_file_stem = build_file_name_stem(id, idx)
            # すでに取得済みであれば, 次のメディアへ
            if self._aws_resource.has_property_item(output_file_stem):
                print(f"skip at {output_file_stem}")
                continue
            img = download_img(extended_entity["media_url_https"])
            if img is None:
                continue
            output_file_path = make_output_path(
                output_dir, created_at, id, idx)
            write_time = write_img(output_file_path, img)
            print(f"write to img -> {output_file_path}")
            self._aws_resource.put_property(
                item={
                    "partition_key": output_file_stem,
                    "created_at": created_at.isoformat(),
                    "text": text,
                    "user_name": user_name,
                    "user_screen_name": user_screen_name,
                    "hashtag": hashtag,
                    "write_time": write_time,
                }
            )
            # Too Many Requests 対策
            time.sleep(3)
            # 1回でもダウンロードした場合False
            is_skip = False
        return is_skip


if __name__ == "__main__":

    param = EnvironParamaters(
        BEARER_TOKEN=os.environ["BEARER_TOKEN"],
        LIKED_USER_ID=os.environ["LIKED_USER_ID"],
        PROPERTY_DB_NAME=os.environ["PROPERTY_DB_NAME"],
        PAGE_TOKE_DB_NAME=os.environ["PAGE_TOKE_DB_NAME"],
        OUTPUT_DIR=os.environ["DIR_NAME"],
        PAGETOKE_RESET=(os.environ["PAGETOKE_RESET"] in [
                        "true", "True", "TRUE"]),
    )
    action = Action(
        env_param=param,
        output_dir=Path(param.OUTPUT_DIR),
    )

    action()
