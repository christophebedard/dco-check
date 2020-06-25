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

import unittest

from dco_check.dco_check import get_default_branch_from_remote
from dco_check.dco_check import main


class TestDcoCheck(unittest.TestCase):

    def __init__(self, *args) -> None:
        super().__init__(
            *args,
        )

    def test_main(self) -> None:
        self.assertEqual(0, main(['-v']))

    def test_get_default_branch_from_remote(self) -> None:
        self.assertEqual('master', get_default_branch_from_remote('origin'))
        self.assertIsNone(get_default_branch_from_remote('this-remote-does-not-exist'))
