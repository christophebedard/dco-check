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
import os
import sys
import unittest
from unittest.mock import patch

from dco_check.dco_check import get_parser
from dco_check.dco_check import Options
from dco_check.dco_check import parse_args


class TestOptionsArgs(unittest.TestCase):

    def __init__(self, *args) -> None:
        super().__init__(
            *args,
        )

    def test_parse_args(self) -> None:
        # To simply test the call itself
        test_argv = ['dco_check/dco_check.py', '-v', '-b', 'my-default-branch']
        with patch.object(sys, 'argv', test_argv):
            args = parse_args()
            self.assertEqual(True, args.verbose)
            self.assertEqual('my-default-branch', args.default_branch)

        test_argv = ['dco_check/dco_check.py', '-q', '-r', 'myawesomeremote']
        with patch.object(sys, 'argv', test_argv):
            args = parse_args()
            self.assertEqual(True, args.quiet)
            self.assertEqual('myawesomeremote', args.default_remote)

    def test_options_basic(self) -> None:
        options = Options(get_parser())
        ns = argparse.Namespace(
            check_merge_commits=True,
            default_branch='b',
            default_branch_from_remote=False,
            default_remote='c',
            quiet=True,
            verbose=False,
        )
        options.set_options(ns)
        self.assertEqual(True, options.check_merge_commits)
        self.assertEqual('b', options.default_branch)
        self.assertEqual(False, options.default_branch_from_remote)
        self.assertEqual('c', options.default_remote)
        self.assertEqual(True, options.quiet)
        self.assertEqual(False, options.verbose)

        self.assertDictEqual(vars(ns), options.get_options())

    @staticmethod
    def reset_environment() -> None:
        env_vars = [
            'DCO_CHECK_CHECK_MERGE_COMMITS',
            'DCO_CHECK_DEFAULT_BRANCH',
            'DCO_CHECK_DEFAULT_BRANCH_FROM_REMOTE',
            'DCO_CHECK_DEFAULT_REMOTE',
            'DCO_CHECK_QUIET',
            'DCO_CHECK_VERBOSE',
        ]
        for env_var in env_vars:
            if env_var in os.environ:
                del os.environ[env_var]

    def test_args_default(self) -> None:
        # Set options through env vars
        self.reset_environment()
        os.environ['DCO_CHECK_CHECK_MERGE_COMMITS'] = 'yessss'
        os.environ['DCO_CHECK_DEFAULT_BRANCH'] = 'adefaultbranch'
        os.environ['DCO_CHECK_DEFAULT_REMOTE'] = 'adefaultremote'
        os.environ['DCO_CHECK_QUIET'] = 'True'
        # os.environ['DCO_CHECK_VERBOSE'] = 'False'
        test_argv = ['dco_check/dco_check.py']
        with patch.object(sys, 'argv', test_argv):
            args = parse_args()
            options = Options(get_parser())
            options.set_options(args)
            self.assertEqual(True, options.check_merge_commits)
            self.assertEqual('adefaultbranch', options.default_branch)
            self.assertEqual('adefaultremote', options.default_remote)
            self.assertEqual(True, options.quiet)
            self.assertEqual(False, options.verbose)

        # Set options through env vars but use some non-default args which should override
        self.reset_environment()
        os.environ['DCO_CHECK_CHECK_MERGE_COMMITS'] = 'yessss'
        os.environ['DCO_CHECK_DEFAULT_BRANCH'] = 'adefaultbranch'
        os.environ['DCO_CHECK_DEFAULT_REMOTE'] = 'adefaultremote'
        os.environ['DCO_CHECK_QUIET'] = 'True'
        # os.environ['DCO_CHECK_VERBOSE'] = 'False'
        test_argv = [
            'dco_check/dco_check.py',
            '--check-merge-commits',  # Same value
            '--default-remote',
            'someremote',
        ]
        with patch.object(sys, 'argv', test_argv):
            args = parse_args()
            options = Options(get_parser())
            options.set_options(args)
            self.assertEqual(True, options.check_merge_commits)
            self.assertEqual('adefaultbranch', options.default_branch)
            self.assertEqual('someremote', options.default_remote)
            self.assertEqual(True, options.quiet)
            self.assertEqual(False, options.verbose)

        # Exits if both quiet and verbose are enabled
        self.reset_environment()
        os.environ['DCO_CHECK_QUIET'] = 'True'
        # os.environ['DCO_CHECK_VERBOSE'] = 'False'
        test_argv = [
            'dco_check/dco_check.py',
            '--verbose',
        ]
        with patch.object(sys, 'argv', test_argv):
            args = parse_args()
            options = Options(get_parser())
            with self.assertRaises(SystemExit):
                options.set_options(args)

        self.reset_environment()
        os.environ['DCO_CHECK_QUIET'] = ''
        os.environ['DCO_CHECK_VERBOSE'] = 'anything means True, even empty'
        test_argv = ['dco_check/dco_check.py']
        with patch.object(sys, 'argv', test_argv):
            args = parse_args()
            options = Options(get_parser())
            with self.assertRaises(SystemExit):
                options.set_options(args)

        # Exits if both --default-branch and --default-branch-from-remote are set to non-default
        self.reset_environment()
        os.environ['DCO_CHECK_DEFAULT_BRANCH'] = 'will evaluate to True'
        test_argv = [
            'dco_check/dco_check.py',
            '--default-branch-from-remote',
        ]
        with patch.object(sys, 'argv', test_argv):
            args = parse_args()
            options = Options(get_parser())
            with self.assertRaises(SystemExit):
                options.set_options(args)

        self.reset_environment()
        os.environ['DCO_CHECK_DEFAULT_BRANCH'] = '69'
        os.environ['DCO_CHECK_DEFAULT_BRANCH_FROM_REMOTE'] = '42'
        test_argv = ['dco_check/dco_check.py']
        with patch.object(sys, 'argv', test_argv):
            args = parse_args()
            options = Options(get_parser())
            with self.assertRaises(SystemExit):
                options.set_options(args)

        self.reset_environment()
