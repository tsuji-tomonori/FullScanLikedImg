from __future__ import annotations

import datetime
from pathlib import Path
import unittest
import os
from unittest import mock


class RebuildUrlTest(unittest.TestCase):

    def test_ok(self):
        # 初期化
        print("RebuildUrlTest")
        before_url = "https://pbs.twimg.com/media/hogehoge.jpg"
        os.environ["BEARER_TOKEN"] = "sample"
        os.environ["LIKED_USER_ID"] = "sample"
        os.environ["DB_NAME"] = "sample"
        os.environ["NEXT_TOKEN"] = "sample"
        os.environ["DIR_NAME"] = "sample"
        from run import rebuild_url
        # テストの実行
        actual = rebuild_url(before_url)
        # アサーション
        self.assertEqual(
            actual, "https://pbs.twimg.com/media/hogehoge?format=png&name=large")
        print("end")


class BuildOutputPathTest(unittest.TestCase):

    @mock.patch("run.Path")
    @mock.patch("os.environ")
    def test_ok(self, os_environ_mock: mock.Mock, path_mock: mock.Mock):
        # 初期化
        print("BuildOutputPathTest")
        os_environ_mock.return_value = "sample"
        output_dir = Path.cwd()
        created_at = datetime.datetime.now()
        id = "123456789"
        index = 0
        from run import make_output_path
        # テストの実行
        actual = make_output_path(output_dir, created_at, id, index)
        # アサーション
        print(actual)
