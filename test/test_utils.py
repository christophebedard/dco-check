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

import os
import unittest

from dco_check.dco_check import extract_name_and_email
from dco_check.dco_check import get_env_var
from dco_check.dco_check import is_valid_email
from dco_check.dco_check import split_commits_data


class TestUtils(unittest.TestCase):

    def __init__(self, *args) -> None:
        super().__init__(
            *args,
        )

    def test_is_valid_email(self) -> None:
        self.assertTrue(is_valid_email('abc@def.hij'))
        self.assertFalse(is_valid_email('@def.hij'))
        self.assertFalse(is_valid_email('abc@.hij'))
        self.assertFalse(is_valid_email('abc@def.'))
        self.assertFalse(is_valid_email('abc@def'))
        self.assertFalse(is_valid_email('abc@'))
        self.assertFalse(is_valid_email(''))
        self.assertFalse(is_valid_email('@'))

    def test_extract_name_and_email(self) -> None:
        self.assertEqual(
            ('Tinky Winky', 'tinky@winky.com'),
            extract_name_and_email('Tinky Winky <tinky@winky.com>'),
        )
        # It doesn't validate the email itself
        self.assertEqual(
            ('Po', 'po'),
            extract_name_and_email('Po <po>'),
        )
        self.assertIsNone(extract_name_and_email(''))
        self.assertIsNone(extract_name_and_email('a <'))
        self.assertIsNone(extract_name_and_email('a >'))
        self.assertIsNone(extract_name_and_email('<>'))
        self.assertIsNone(extract_name_and_email('<abc>'))

    def test_get_env_var(self) -> None:
        self.assertIsNone(get_env_var(''))
        self.assertIsNone(get_env_var('THIS_PROBABLY_DOES_NOT_EXIST', print_if_not_found=True))
        self.assertIsNone(get_env_var('THIS_PROBABLY_DOES_NOT_EXIST', print_if_not_found=False))
        self.assertEqual(
            'abc',
            get_env_var('THIS_PROBABLY_DOES_NOT_EXIST', default='abc', print_if_not_found=True),
        )
        self.assertEqual(
            'abc',
            get_env_var('THIS_PROBABLY_DOES_NOT_EXIST', default='abc', print_if_not_found=False),
        )
        self.assertEqual('', get_env_var('THIS_PROBABLY_DOES_NOT_EXIST', default=''))

        os.environ['THIS_WILL_EXIST'] = 'xyz'
        self.assertEqual('xyz', get_env_var('THIS_WILL_EXIST'))
        self.assertEqual('xyz', get_env_var('THIS_WILL_EXIST', default='abc'))

    def test_split_commits_data(self) -> None:
        # This is just a split on a string, but let's test it anyway
        data = (
            'abc'
            '\x1e'
            'def'
        )
        self.assertEqual(['abc', 'def'], split_commits_data(data))
        data = (
            'abc'
            '\x1e'
            'def'
            '\x1e'
        )
        self.assertEqual(['abc', 'def'], split_commits_data(data))
