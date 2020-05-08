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
import unittest

from dco_check.dco_check import BooleanDefaultValue
from dco_check.dco_check import get_parser
from dco_check.dco_check import Options
from dco_check.dco_check import StringDefaultValue
from dco_check.dco_check import wrap_default_value


class TestOptionsArgs(unittest.TestCase):

    def __init__(self, *args) -> None:
        super().__init__(
            *args,
        )

    def test_options_basic(self) -> None:
        options = Options(get_parser())
        ns = argparse.Namespace(
            check_merge_commits=True,
            default_branch='b',
            default_remote='c',
            quiet=True,
            verbose=False,
        )
        options.set_options(ns)
        self.assertEqual(True, options.check_merge_commits)
        self.assertEqual('b', options.default_branch)
        self.assertEqual('c', options.default_remote)
        self.assertEqual(True, options.quiet)
        self.assertEqual(False, options.verbose)

    def test_options_default(self) -> None:
        ns_default = argparse.Namespace(
            check_merge_commits=BooleanDefaultValue(False),
            default_branch=StringDefaultValue('b'),
            default_remote=StringDefaultValue('c'),
            quiet=BooleanDefaultValue(False),
            verbose=BooleanDefaultValue(False),
        )

        # Default arg values
        options = Options(get_parser())
        options.set_options(ns_default)
        self.assertEqual(False, bool(options.check_merge_commits))
        self.assertEqual('b', options.default_branch)
        self.assertEqual('c', options.default_remote)
        self.assertEqual(False, bool(options.quiet))
        self.assertEqual(False, bool(options.verbose))

        # Set options through env vars
        os.environ['DCO_CHECK_CHECK_MERGE_COMMITS'] = 'True'
        os.environ['DCO_CHECK_DEFAULT_BRANCH'] = 'adefaultbranch'
        os.environ['DCO_CHECK_DEFAULT_REMOTE'] = 'adefaultremote'
        os.environ['DCO_CHECK_QUIET'] = 'True'
        os.environ['DCO_CHECK_VERBOSE'] = 'False'
        options.apply_env_vars()
        self.assertEqual(True, options.check_merge_commits)
        self.assertEqual('adefaultbranch', options.default_branch)
        self.assertEqual('adefaultremote', options.default_remote)
        self.assertEqual(True, options.quiet)
        self.assertEqual(False, options.verbose)

        # Set options through env vars but use non-default args which should override
        options = Options(get_parser())
        options.set_options(ns_default)
        self.assertEqual(False, bool(options.check_merge_commits))
        self.assertEqual('b', options.default_branch)
        self.assertEqual('c', options.default_remote)
        self.assertEqual(False, bool(options.quiet))
        self.assertEqual(False, bool(options.verbose))

        os.environ['DCO_CHECK_CHECK_MERGE_COMMITS'] = 'False'
        os.environ['DCO_CHECK_DEFAULT_BRANCH'] = 'adefaultbranch'
        os.environ['DCO_CHECK_DEFAULT_REMOTE'] = 'adefaultremote'
        os.environ['DCO_CHECK_QUIET'] = 'False'
        os.environ['DCO_CHECK_VERBOSE'] = 'False'
        options.apply_env_vars()
        self.assertEqual(False, options.check_merge_commits)
        self.assertEqual('adefaultbranch', options.default_branch)
        self.assertEqual('adefaultremote', options.default_remote)
        self.assertEqual(False, options.quiet)
        self.assertEqual(False, options.verbose)

        non_default = argparse.Namespace(
            check_merge_commits=True,
            default_branch='bbb',
            default_remote='ccc',
            quiet=False,
            verbose=True,
        )
        options.set_options(non_default)
        self.assertEqual(True, options.check_merge_commits)
        self.assertEqual('bbb', options.default_branch)
        self.assertEqual('ccc', options.default_remote)
        self.assertEqual(False, options.quiet)
        self.assertEqual(True, options.verbose)

        # Raises if both quiet and verbose are enabled
        options = Options(get_parser())
        options.set_options(ns_default)
        os.environ['DCO_CHECK_QUIET'] = 'True'
        os.environ['DCO_CHECK_VERBOSE'] = 'True'
        with self.assertRaises(ValueError):
            options.apply_env_vars()
