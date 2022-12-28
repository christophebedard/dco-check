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
import copy
import unittest

from dco_check.dco_check import check_infractions
from dco_check.dco_check import CommitInfo
from dco_check.dco_check import options
from dco_check.dco_check import process_commits


class TestProcessing(unittest.TestCase):

    def __init__(self, *args) -> None:
        super().__init__(
            *args,
        )

    def test_check_infractions(self) -> None:
        self.assertEqual(0, check_infractions({}))
        self.assertEqual(1, check_infractions({'abcd': ['some', 'errors']}))
        self.assertEqual(1, check_infractions({'abcd': []}))

    def test_process_commits(self) -> None:
        # No commits
        commits = []
        self.assertEqual(0, len(process_commits(commits, False)))
        # Signed-off comits
        commits = [
            CommitInfo(
                'adc',
                'This is a commit title',
                [
                    'some description about the commit',
                    'Signed-off-by: Tinky Winky <tinky@winky.com>',
                ],
                'Tinky Winky',
                'tinky@winky.com',
                False,
            ),
            CommitInfo(
                'def',
                'This is another commit title',
                ['Signed-off-by: Laa-Laa <laa@laa.laa>'],
                'Laa-Laa',
                'laa@laa.laa',
                False,
            )
        ]
        self.assertEqual(0, len(process_commits(commits, False)))
        # Merge commit that isn't signed-off but is ignored
        commits = [
            CommitInfo(
                'adc',
                'This is a merge commit title',
                [''],
                'Tinky Winky',
                'tinky@winky.com',
                True,
            ),
            CommitInfo(
                'def',
                'This is another commit title',
                ['Signed-off-by: Laa-Laa <laa@laa.laa>'],
                'Laa-Laa',
                'laa@laa.laa',
                False,
            )
        ]
        self.assertEqual(0, len(process_commits(commits, False)))
        # Merge commit that isn't signed-off but is NOT ignored
        commits = [
            CommitInfo(
                'adc',
                'This is a merge commit title',
                [''],
                'Tinky Winky',
                'tinky@winky.com',
                True,
            ),
            CommitInfo(
                'def',
                'This is another commit title',
                ['Signed-off-by: Laa-Laa <laa@laa.laa>'],
                'Laa-Laa',
                'laa@laa.laa',
                False,
            )
        ]
        self.assertEqual(1, len(process_commits(commits, True)))
        # Invalid author name/email
        commits = [
            CommitInfo(
                'adc',
                'This is a commit title',
                ['Signed-off-by: Tinky Winky <tinky@winky.com>'],
                None,
                None,
                False,
            ),
        ]
        self.assertEqual(1, len(process_commits(commits, False)))
        # No sign-off
        commits = [
            CommitInfo(
                'adc',
                'This is a commit title',
                [''],
                'Tinky Winky',
                'tinky@winky.com',
                False,
            ),
        ]
        self.assertEqual(1, len(process_commits(commits, False)))
        commits = [
            CommitInfo(
                'adc',
                'This is a commit title',
                [],
                'Tinky Winky',
                'tinky@winky.com',
                False,
            ),
        ]
        self.assertEqual(1, len(process_commits(commits, False)))
        # Invalid sign-off email
        commits = [
            CommitInfo(
                'adc',
                'This is a commit title',
                ['Signed-off-by: Tinky Winky <winky.com>'],
                'Tinky Winky',
                'tinky@winky.com',
                False,
            ),
        ]
        self.assertEqual(1, len(process_commits(commits, False)))
        # Sign-off doesn't match author
        commits = [
            CommitInfo(
                'adc',
                'This is a commit title',
                ['Signed-off-by: Tinky Winky <winky.com>'],
                'Laa-Laa',
                'laa@laa.laa',
                False,
            ),
        ]
        self.assertEqual(1, len(process_commits(commits, False)))
        # Multiple failures
        commits = [
            CommitInfo(
                'adc',
                'This is a commit title',
                ['Signed-off-by: Tinky Winky <winky.com>'],
                'Laa-Laa',
                'laa@laa.laa',
                False,
            ),
            CommitInfo(
                'def',
                'This is a commit title',
                ['Signed-off-by: Tinky Winky <winky.com>'],
                'Tinky Winky',
                'tinky@winky.com',
                False,
            ),
            CommitInfo(
                'ghi',
                'This is a merge commit title',
                [],
                'Tinky Winky',
                'tinky@winky.com',
                True,
            ),
        ]
        self.assertEqual(3, len(process_commits(commits, True)))

    def test_process_commits_exclude_email(self) -> None:
        global options
        original_options = copy.copy(options)

        ns = argparse.Namespace(
            check_merge_commits=True,
            default_branch='b',
            default_branch_from_remote=False,
            default_remote='c',
            exclude_emails='laa@laa.laa,tinky@winky.com',
            exclude_pattern='gen\\[bot\\]@gmail\\.com',
            quiet=False,
            verbose=False,
        )
        options.set_options(ns)

        # No sign-off but author email is in exclude emails list
        commits = [
            CommitInfo(
                'adc',
                'This is a commit title',
                [],
                'Laa-Laa',
                'laa@laa.laa',
                False,
            ),
        ]
        self.assertEqual(0, len(process_commits(commits, False)))

        # No sign-offs but one commit has its author email is in exclude emails list
        commits = [
            CommitInfo(
                'adc',
                'This is a commit title',
                [],
                'Laa-Laa',
                'laa@laa.laa',
                False,
            ),
            CommitInfo(
                'def',
                'This is another commit title',
                [],
                'Po',
                'po@p.o',
                False,
            ),
        ]
        self.assertEqual(1, len(process_commits(commits, False)))

        # Signed-off but author email is still in exclude emails list
        commits = [
            CommitInfo(
                'adc',
                'This is a commit title',
                ['Signed-off-by: Laa-Laa <laa@laa.laa>'],
                'Laa-Laa',
                'laa@laa.laa',
                False,
            ),
        ]
        self.assertEqual(0, len(process_commits(commits, False)))
        
        # Signed-off but author email is matched with exclude pattern
        commits = [
            CommitInfo(
                'adc',
                'This is a commit title',
                ['Signed-off-by: genericbot <[bot]@gmail.com>'],
                'generic_bot',
                '277373_gen[bot]@gmail.com',
                False,
            ),
        ]
        self.assertEqual(0, len(process_commits(commits, False)))

        options = original_options
