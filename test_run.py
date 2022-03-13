from __future__ import annotations

import datetime
from pathlib import Path
import unittest
from unittest import mock

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
        expect = "2022-02-19T00:00:00+09:00"
        from run import now_isof
        # テストの実行
        actual = now_isof()
        # アサーション
        self.assertEqual(actual, expect)
