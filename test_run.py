from __future__ import annotations

import datetime
from pathlib import Path
import unittest
import os
from unittest import mock


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


class BuildOutputPathTest(unittest.TestCase):

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
