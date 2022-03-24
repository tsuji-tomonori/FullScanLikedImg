from __future__ import annotations

import datetime
import os
from pathlib import Path
import unittest
from unittest import mock

import boto3
from moto import mock_dynamodb, mock_ssm
from freezegun import freeze_time


class RebuildUrlTest(unittest.TestCase):

    def test_ok(self):
        # 初期化
        before_url = "https://pbs.twimg.com/media/hogehoge.jpg"
        from run import rebuild_url
        # テストの実行
        actual = rebuild_url(before_url)
        # アサーション
        self.assertEqual(
            actual, "https://pbs.twimg.com/media/hogehoge?format=png&name=large")


class MakeOutputPathTest(unittest.TestCase):

    @mock.patch("run.Path.mkdir")
    def test_ok(self, path_mock: mock.Mock):
        # 初期化
        output_dir = Path.cwd()
        created_at = datetime.datetime(2022, 3, 13, 1)
        id = "123456789"
        index = 0
        expect = Path.cwd() / "yyyy=2022" / "mm=03" / \
            "dd=13" / "123456789_0.png"
        from run import make_output_path
        # テストの実行
        actual = make_output_path(output_dir, created_at, id, index)
        # アサーション
        self.assertEqual(actual, expect)
        self.assertEqual(len(path_mock.call_args_list), 4)


class ToJstTimezoneTest(unittest.TestCase):

    def test_ok(self):
        # 初期化
        timestr = "Sat Feb 19 11:11:44 +0000 2022"
        format = "%a %b %d %H:%M:%S +0000 %Y"
        expect = datetime.datetime(2022, 2, 19, 20, 11, 44).astimezone(
            datetime.timezone(datetime.timedelta(hours=9)))
        from run import to_jst_timezone
        # テストの実行
        actual = to_jst_timezone(timestr, format)
        # アサーション
        self.assertEqual(str(actual.tzinfo), "UTC+09:00")
        self.assertEqual(actual, expect)


class TwitterToJstTimezone(unittest.TestCase):

    def test_ok(self):
        # 初期化
        timestr = "Sat Feb 19 11:11:44 +0000 2022"
        expect = datetime.datetime(2022, 2, 19, 20, 11, 44).astimezone(
            datetime.timezone(datetime.timedelta(hours=9)))
        from run import twitter_to_jst_timezone
        # テストの実行
        actual = twitter_to_jst_timezone(timestr)
        # アサーション
        self.assertEqual(actual, expect)


class NowIsofTest(unittest.TestCase):

    @freeze_time("2022-02-19 00:00:00+00:00")
    def test_ok(self):
        # 初期化
        expect = "2022-02-19T09:00:00+09:00"
        from run import now_isof
        # テストの実行
        actual = now_isof()
        # アサーション
        self.assertEqual(actual, expect)


class WriteImgTest(unittest.TestCase):

    @freeze_time("2022-02-19 00:00:00+00:00")
    @mock.patch("run.Path.open")
    def test_ok(self, path_open_mock: mock.Mock):
        # 初期化
        path = Path.cwd()
        data = bin(123)
        expect = "2022-02-19T09:00:00+09:00"
        from run import write_img
        # テストの実行
        actual = write_img(path, data)
        # アサーション
        self.assertEqual(actual, expect)
        self.assertEqual(path_open_mock.call_args[0][0], "wb")


class HashtagsToStrTest(unittest.TestCase):

    def test_ok_one(self):
        # 初期化
        hashtags = [
            {
                "text": "ノエラート",
                "indices": [
                    4,
                    10
                ]
            }
        ]
        expect = "ノエラート"
        from run import hashtags_to_str
        # テストの実行
        actual = hashtags_to_str(hashtags)
        # アサーション
        self.assertEqual(actual, expect)

    def test_ok_two(self):
        # 初期化
        hashtags = [
            {
                "text": "原神",
                "indices": [
                    7,
                    10
                ]
            },
            {
                "text": "GenshinImpact",
                "indices": [
                    11,
                    25
                ]
            }
        ]
        expect = "原神,GenshinImpact"
        from run import hashtags_to_str
        # テストの実行
        actual = hashtags_to_str(hashtags)
        # アサーション
        self.assertEqual(actual, expect)

    def test_ok_none(self):
        # 初期化
        hashtags = []
        expect = ""
        from run import hashtags_to_str
        # テストの実行
        actual = hashtags_to_str(hashtags)
        # アサーション
        self.assertEqual(actual, expect)


class AwsResourceTest(unittest.TestCase):

    def setUp(self) -> None:
        from run import EnvironParamaters
        self.env_param = EnvironParamaters(
            BEARER_TOKEN="BEARER_TOKEN",
            LIKED_USER_ID="LIKED_USER_ID",
            PROPERTY_DB_NAME="PROPERTY_DB_NAME",
            PAGE_TOKE_DB_NAME="PAGE_TOKE_DB_NAME",
            OUTPUT_DIR="OUTPUT_DIR",
            PAGETOKE_RESET="false",
        )

        # 安全のためクレデンシャル周りをテスト用に
        os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
        os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
        os.environ['AWS_SECURITY_TOKEN'] = 'testing'
        os.environ['AWS_SESSION_TOKEN'] = 'testing'
        os.environ['AWS_DEFAULT_REGION'] = 'ap-northeast-1'

    @mock_ssm
    def test_get_value_from_ssm(self):
        # 初期化
        from run import AwsResource
        aws_resource = AwsResource(self.env_param)
        # 仮想のパラメータストアを作成
        ssm = boto3.client("ssm")
        ssm.put_parameter(Name='BEARER_TOKEN',
                          Value='BEARER_TOKEN_SSM', Type='SecureString')
        key = "BEARER_TOKEN"
        expect = "BEARER_TOKEN_SSM"
        # テストの実行
        actual = aws_resource.get_value_from_ssm(key)
        # アサーション
        self.assertEqual(actual, expect)

    @mock_dynamodb
    def test_put_property(self):
        # 初期化
        from run import AwsResource
        aws_resource = AwsResource(self.env_param)
        # 仮想のDynamoDB テーブルを作成
        dynamodb = boto3.resource('dynamodb')
        table = self.create_table(
            dynamodb, "PROPERTY_DB_NAME", "partition_key")
        expect = self.sample_property()
        # テストの実行
        aws_resource.put_property(expect)
        # アサーション
        actual = table.get_item(
            Key={
                "partition_key": "1293399653283557377_0"
            }
        )
        self.assertDictEqual(actual["Item"], expect)

    @mock_dynamodb
    def test_has_property_item_exist(self):
        # 初期化
        from run import AwsResource
        aws_resource = AwsResource(self.env_param)
        # 仮想のDynamoDB テーブルを作成
        dynamodb = boto3.resource('dynamodb')
        table = self.create_table(
            dynamodb, "PROPERTY_DB_NAME", "partition_key")
        # 仮想のDynamoDBにItemをput
        table.put_item(
            Item=self.sample_property()
        )
        # テストの実行
        actual = aws_resource.has_property_item("1293399653283557377_0")
        # アサーション
        self.assertTrue(actual)

    @mock_dynamodb
    def test_has_property_item_not_exist(self):
        # 初期化
        from run import AwsResource
        aws_resource = AwsResource(self.env_param)
        # 仮想のDynamoDB テーブルを作成
        dynamodb = boto3.resource('dynamodb')
        table = self.create_table(
            dynamodb, "PROPERTY_DB_NAME", "partition_key")
        # 仮想のDynamoDBにItemをput
        table.put_item(
            Item=self.sample_property()
        )
        # テストの実行
        actual = aws_resource.has_property_item("hogehoge")
        # アサーション
        self.assertFalse(actual)

    @mock_dynamodb
    def test_get_pagetoken(self):
        # 初期化
        from run import AwsResource
        aws_resource = AwsResource(self.env_param)
        # 仮想のDynamoDB テーブルを作成
        dynamodb = boto3.resource('dynamodb')
        table = self.create_table(
            dynamodb, "PAGE_TOKE_DB_NAME", "liked_user_id")
        # 仮想のDynamoDBにItemをput
        table.put_item(
            Item=self.sample_pagetoken()
        )
        # テストの実行
        actual = aws_resource.get_pagetoken()
        # アサーション
        self.assertEqual(
            actual, "7140dibdnow9c7btw452upxk1q3s65hih3b8ebx3hoge")

    @freeze_time("2022-03-18 06:51:13.737285+00:00", tz_offset=datetime.timedelta(hours=0))
    @mock_dynamodb
    def test_put_pagetoken(self):
        # 初期化
        from run import AwsResource
        aws_resource = AwsResource(self.env_param)
        # 仮想のDynamoDB テーブルを作成
        dynamodb = boto3.resource('dynamodb')
        table = self.create_table(
            dynamodb, "PAGE_TOKE_DB_NAME", "liked_user_id")

        # テストの実行
        aws_resource.put_pagetoken(
            "7140dibdnow9c7btw452upxk1q3s65hih3b8ebx3hoge")
        # アサーション
        actual = table.get_item(
            Key={
                "liked_user_id": "LIKED_USER_ID"
            }
        )
        self.assertEqual(actual["Item"], self.sample_pagetoken())

    def create_table(self, dynamodb: boto3.resource, table_name: str, partition_key: str) -> boto3.resources.factory.dynamodb.Table:
        return dynamodb.create_table(
            TableName=table_name,
            KeySchema=[
                {
                    'AttributeName': partition_key,
                    'KeyType': 'HASH'
                }
            ],
            AttributeDefinitions=[
                {
                    'AttributeName': partition_key,
                    'AttributeType': 'S'
                }
            ],
            BillingMode='PROVISIONED',
            ProvisionedThroughput={
                'ReadCapacityUnits': 1,
                'WriteCapacityUnits': 1
            },
        )

    def sample_property(self) -> dict:
        return {
            "partition_key": "1293399653283557377_0",
            "created_at": "2020-08-12T22:11:22+09:00",
            "text": "夏",
            "user_name": "user_name",
            "user_screen_name": "user_screen_name",
            "hashtag": "hashtag",
            "write_time": "2022-03-17T13:46:01.965558+09:00",
        }

    def sample_pagetoken(self) -> dict:
        return {
            "liked_user_id": "LIKED_USER_ID",
            "page_token": "7140dibdnow9c7btw452upxk1q3s65hih3b8ebx3hoge",
            "timestamp": "2022-03-18T15:51:13.737285+09:00"
        }
