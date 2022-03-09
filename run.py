import datetime
import os
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

import boto3

from src.twitter_api import DoseNotExistException, TwitterApi

# 環境変数
BEARER_TOKEN = os.environ["BEARER_TOKEN"]
LIKED_USER_ID = os.environ["LIKED_USER_ID"]
DB_NAME = os.environ["DB_NAME"]
NEXT_TOKEN = os.environ["NEXT_TOKEN"]
DIR_NAME = os.environ["DIR_NAME"]


# boto3周り
ssm_client = boto3.client("ssm")
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(DB_NAME)


def get_value_from_ssm(ssm_client: boto3.client, key: str) -> str:
    value = ssm_client.get_parameter(
        Name=key,
        WithDecryption=True
    )
    return value["Parameter"]["Value"]


def put_db(db_resource: boto3.resource, item: dict) -> None:
    db_resource.put_item(
        Item=item
    )


def has_item(db_resource: boto3.resource, key: str) -> bool:
    res = db_resource.get_item(
        Key={
            "partition_key": key
        }
    )
    return bool(res.get("Item"))


def tag_strf_query_paramater(tag: dict) -> str:
    return "&".join(f"{k}={v}" for k, v in tag.items())


def to_jst_timezone(timestr: str, format: str) -> datetime.datetime:
    tt = datetime.datetime.strptime(timestr, format)
    jst_delta = datetime.timedelta(hours=9)
    jst_zone = datetime.timezone(jst_delta)
    tt += jst_delta
    return tt.astimezone(jst_zone)


def twitter_to_jst_timezone(time_str: str) -> datetime.datetime:
    return to_jst_timezone(time_str, "%a %b %d %H:%M:%S +0000 %Y")


def now_isof() -> str:
    now = datetime.datetime.now()
    jst_delta = datetime.timedelta(hours=9)
    jst_zone = datetime.timezone(jst_delta)
    return now.astimezone(jst_zone).isoformat()


def write_img(path: Path, data: bin) -> str:
    with path.open("wb") as f:
        f.write(data)
    return now_isof()


def download_img(url: str) -> bin:
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
            else:
                raise e
    # リトライオーバー
    print("Retry Limit.")
    raise exception


def rebuild_url(before_url: str) -> str:
    # https://pbs.twimg.com/media/hogehoge.jpg
    # https://pbs.twimg.com/media/hogehoge?format=png&name=large
    # に変更することで, 大きなpng画像を取得することが出来る
    return f"{before_url[:-4]}?format=png&name=large"


def build_output_path(output_dir: Path, created_at: datetime.datetime, id: str, index: int) -> Path:
    result = output_dir
    result.mkdir(exist_ok=True)
    result /= f"yyyy={created_at.year}"
    result.mkdir(exist_ok=True)
    result /= f"mm={str(created_at.month).zfill(2)}"
    result.mkdir(exist_ok=True)
    result /= f"dd={str(created_at.day).zfill(2)}"
    result.mkdir(exist_ok=True)
    result /= f"{id}_{index}.png"
    return result


def hashtags_to_str(hashtags: list) -> str:
    return ",".join(hashtag["text"] for hashtag in hashtags)


def downdload_and_write_db(tweet_info: dict, output_dir: Path) -> None:
    id = tweet_info["id_str"]
    text = tweet_info["text"]
    user_name = tweet_info["user"]["name"]
    user_screen_name = tweet_info["user"]["screen_name"]
    hashtag = hashtags_to_str(tweet_info["entities"]["hashtags"])
    created_at = twitter_to_jst_timezone(tweet_info["created_at"])
    # 1ツイート内で投稿されている画像分ループ
    for idx, extended_entity in enumerate(tweet_info["extended_entities"]["media"]):
        # 投稿されたメディアが画像でない場合, 次のtweetへ
        if extended_entity["type"] != "photo":
            continue
        output_file = build_output_path(output_dir, created_at, id, idx)
        # すでに取得済みであれば, 次のtweetへ
        if has_item(table, output_file.stem):
            print(f"skip at {output_file}")
            continue
        img = download_img(extended_entity["media_url_https"])
        write_time = write_img(output_file, img)
        print(f"write to img -> {output_file}")
        put_db(
            db_resource=table,
            item={
                "partition_key": output_file.stem,
                "created_at": created_at.isoformat(),
                "text": text,
                "user_name": user_name,
                "user_screen_name": user_screen_name,
                "hashtag": hashtag,
                "write_time": write_time,
            }
        )


def service(output_dir: Path, next_token: str = None) -> None:

    bearer_token = get_value_from_ssm(ssm_client, BEARER_TOKEN)
    api = TwitterApi(bearer_token=bearer_token)

    while True:
        ids = api.get_liked_tweets(LIKED_USER_ID, next_token)
        # いいねが取得できなかった場合, 処理終了
        if len(ids["data"]) == 0:
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
                downdload_and_write_db(tweet_info, output_dir)
            except Exception as e:
                # Twitter API 周り以外で例外が発生した場合
                # 先にnext_tokenを表示させる
                print(f"Current next token is: {next_token}")
                raise e
        next_token = ids["meta"]["next_token"]
        # Too Many Requests 対策
        print(f"sleep at 12 sec... next token is: {next_token}")
        time.sleep(12)


def handler(output_dir: Path, next_token: str) -> None:
    print(f"service start! target liked user id is {LIKED_USER_ID}")
    print(f"start at: {now_isof()}")
    try:
        service(
            output_dir=output_dir,
            next_token=next_token,
        )
    except Exception as e:
        print(f"An Error occurrence at: {now_isof()}")
        raise e
    print(f"end at: {now_isof()}")


if __name__ == "__main__":
    handler(
        output_dir=Path.cwd() / DIR_NAME,
        next_token=None if NEXT_TOKEN == "" else NEXT_TOKEN,
    )
