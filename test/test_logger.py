# Copyright 2020 Christophe Bedard
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse
from io import StringIO
import unittest
from unittest.mock import patch

from dco_check.dco_check import get_parser
from dco_check.dco_check import Logger
from dco_check.dco_check import Options


class TestLogger(unittest.TestCase):

    def __init__(self, *args) -> None:
        super().__init__(
            *args,
        )

    def test_logger(self) -> None:
        ns = argparse.Namespace(
            check_merge_commits=False,
            default_branch='b',
            default_branch_from_remote=False,
            default_remote='c',
            quiet=False,
            verbose=False,
        )
        options = Options(get_parser())
        options.set_options(ns)

        l = Logger(get_parser())
        l.set_options(options)

        # Not quiet, not verbose
        with patch('sys.stdout', new=StringIO()) as fake_stdout:
            l.print('abcdef')
            self.assertEqual('abcdef', fake_stdout.getvalue().strip())
        with patch('sys.stdout', new=StringIO()) as fake_stdout:
            l.verbose_print('123456')
            self.assertEqual('', fake_stdout.getvalue().strip())

        # Verbose
        ns = argparse.Namespace(
            check_merge_commits=False,
            default_branch='b',
            default_branch_from_remote=False,
            default_remote='c',
            quiet=False,
            verbose=True,
        )
        options.set_options(ns)
        l.set_options(options)
        with patch('sys.stdout', new=StringIO()) as fake_stdout:
            l.verbose_print('123456')
            self.assertEqual('123456', fake_stdout.getvalue().strip())

        # Quiet
        ns = argparse.Namespace(
            check_merge_commits=False,
            default_branch='b',
            default_branch_from_remote=False,
            default_remote='c',
            quiet=True,
            verbose=False,
        )
        options.set_options(ns)
        l.set_options(options)
        with patch('sys.stdout', new=StringIO()) as fake_stdout:
            l.print('abcdef')
            self.assertEqual('', fake_stdout.getvalue().strip())
        with patch('sys.stdout', new=StringIO()) as fake_stdout:
            l.verbose_print('123456')
            self.assertEqual('', fake_stdout.getvalue().strip())
