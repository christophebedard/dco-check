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

"""Check that all commits for a proposed change are signed off."""

import argparse
from collections import defaultdict
import os
import re
import subprocess
import sys
from typing import Any
from typing import Callable
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple


TRAILER_KEY_SIGNED_OFF_BY = 'Signed-off-by:'
DEFAULT_DEFAULT_BRANCH = 'master'


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Check that all commits of a proposed change have a DCO (i.e. are signed-off)',
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        default=False,
        help='verbose mode (print out more information)',
    )
    return parser.parse_args()


def is_valid_email(
    email: str,
) -> bool:
    """
    Check if email is valid.

    Simple regex checking for:
        <nonwhitespace string>@<nonwhitespace string>.<nonwhitespace string>

    :param email: the email address to check
    :return: true if email is valid, false otherwise
    """
    return re.match(r'^\S+@\S+\.\S+', email)


def get_head_commit_sha() -> Optional[str]:
    """
    Get the sha of the HEAD commit.

    :return: the sha of the HEAD commit, or `None` if it failed
    """
    command = [
        'git',
        'rev-parse',
        '--verify',
        'HEAD',
    ]
    run_output = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding='UTF-8',
    )
    if run_output.returncode != 0:
        print(f'error: {run_output.stdout}')
        return None
    return run_output.stdout.strip('\n')


def get_common_ancestor_commit_sha(
    base_ref: str,
) -> Optional[str]:
    """
    Get the common ancestor commit of the current commit and a given reference.

    See: git merge-base --fork-point

    :param base_ref: the other reference
    :return: the common ancestor commit, or `None` if it failed
    """
    command = [
        'git',
        'merge-base',
        '--fork-point',
        base_ref,
    ]
    run_output = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding='UTF-8',
    )
    if run_output.returncode != 0:
        print(f'error: {run_output.stdout}')
        return None
    return run_output.stdout.strip('\n')


def get_commits_data(
    commit_sha_before: str,
    commit_sha: str,
) -> Optional[str]:
    """
    Get data (full sha & commit body) for commits in a range.

    The range excludes the 'before' commit, e.g. ]commit_sha_before, commit_sha]
    The output data contains data for individual commits, separated by special characters:
       * 1st line: full commit sha
       * 2nd line: author name and email
       * subsequent lines: commit body (which excludes the commit title line)
       * record separator (0x1e)

    :param commit_sha_before: the sha of the commit just before the start of the range
    :param commit_sha: the sha of the last commit of the range
    :return: the data, or `None` if it failed
    """
    command = [
        'git',
        'log',
        f'{commit_sha_before}..{commit_sha}',
        '--pretty=%H%n%an <%ae>%n%-b%x1e',
    ]
    run_output = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding='UTF-8',
    )
    if run_output.returncode != 0:
        print(f'error: {run_output.stdout}')
        return None
    return run_output.stdout


def split_commits_data(
    commits_data: str,
    commits_sep: str = '\x1e',
) -> List[str]:
    """
    Split data into individual commits using a separator.

    :param commits_data: the full data to be split
    :param commits_sep: the string which separates individual commits
    :return: the list of data for each individual commit
    """
    # Remove leading/trailing newlines
    commits_data = commits_data.strip('\n')
    # Split in individual commits and remove leading/trailing newlines
    individual_commits = [single_output.strip('\n') for single_output in commits_data.split(commits_sep)]
    # Filter out empty elements
    individual_commits = list(filter(None, individual_commits))
    return individual_commits


def extract_name_and_email(
    name_and_email: str,
) -> Optional[Tuple[str, str]]:
    """
    Extract a name and an email from a 'name <email>' string.

    :param name_and_email: the name and email string
    :return: the extracted (name, email) tuple, or `None` if it failed
    """
    email_match = re.search('<(.*)>', name_and_email)
    if email_match is None:
        return None
    name_match = re.search('(.*) <', name_and_email)
    if name_match is None:
        return None
    return name_match.group(1), email_match.group(1)


def get_env_var(
    env_var: str,
    print_if_not_found: bool = True,
    default: str = None,
) -> Optional[str]:
    """
    Get the value of an environment variable.

    :param env_var: the environment variable name/key
    :param print_if_not_found: whether to print if the environment variable could not be found
    :param default: the value to use if the environment variable could not be found
    :return: the environment variable value, or `None` if not found and no default value was given
    """
    value = os.environ.get(env_var, None)
    if value is None:
        if default is not None:
            if print_if_not_found:
                print(f'could not get environment variable: \'{env_var}\'; using value default value: \'{default}\'')
            value = default
        elif print_if_not_found:
            print(f'could not get environment variable: \'{env_var}\'')
    return value


def get_commits(
    verbose_print: Callable[[Any], None],
) -> Optional[Tuple[str, str]]:
    """
    Get the range of commits to be checked: (last commit that was checked, latest commit).

    The range excludes the first commit, e.g. ]first commit, second commit]

    :param verbose_print: the function to use for verbose prints
    :return the (last commit that was checked, latest commit) tuple, or `None` if it failed
    """
    if get_env_var('GITLAB_CI', print_if_not_found=False) is not None:
        print('detected GitLab CI')
        # See: https://docs.gitlab.com/ee/ci/variables/predefined_variables.html
        default_branch = get_env_var('CI_DEFAULT_BRANCH', default=DEFAULT_DEFAULT_BRANCH)

        commit_sha = get_env_var('CI_COMMIT_SHA')
        if commit_sha is None:
            return None

        # If we're on the default branch, just test new commits
        current_branch = get_env_var('CI_COMMIT_BRANCH')
        if current_branch is not None and current_branch == default_branch:
            verbose_print(f'on default branch \'{current_branch}\': will check new commits')
            commit_sha_before = get_env_var('CI_COMMIT_BEFORE_SHA')
            if commit_sha_before is None:
                return None
            return commit_sha_before, commit_sha
        else:
            # Otherwise test all commits off of the default branch
            verbose_print(f'on branch \'{current_branch}\': will check forked commits off of default branch \'{default_branch}\'')
            commit_sha_before = get_common_ancestor_commit_sha(default_branch)
            if commit_sha_before is None:
                return None
            return commit_sha_before, commit_sha
    else:
        print(f'could not detect CI, falling back to default base branch: {DEFAULT_DEFAULT_BRANCH}')
        commit_sha_before = get_common_ancestor_commit_sha(DEFAULT_DEFAULT_BRANCH)
        if commit_sha_before is None:
            return None
        commit_sha = get_head_commit_sha()
        if commit_sha is None:
            return None
        return commit_sha_before, commit_sha


def main() -> int:
    args = parse_args()
    verbose = args.verbose

    def verbose_print(msg, *args, **kwargs) -> None:
        if verbose:
            print(msg, *args, **kwargs)

    commits = get_commits(verbose_print)
    if commits is None:
        return 1
    commit_sha_before, commit_sha = commits
    verbose_print(f'commits: {commit_sha_before}..{commit_sha}')

    commits_data = get_commits_data(commit_sha_before, commit_sha)
    verbose_print('commits_data:', ('\n' + commits_data.strip('\n')).replace('\n', '\n\t'))
    if commits_data is None:
        return 1

    individual_commits = split_commits_data(commits_data)
    verbose_print('individual_commits:', individual_commits)

    infractions: Dict[str, List[str]] = defaultdict(list)
    for commit_data in individual_commits:
        commit_lines = commit_data.split('\n')
        commit_sha = commit_lines[0]
        verbose_print('commit_sha:', commit_sha)
        commit_author_data = commit_lines[1]
        verbose_print('commit_author_data:', commit_author_data)
        commit_body = commit_lines[2:]
        verbose_print('commit_body:', commit_body)

        # Extract author name and email
        author_result = extract_name_and_email(commit_author_data)
        if author_result is None:
            infractions[commit_sha].append(f'could not extract author data: {commit_author_data}')
            continue

        # Extract sign off data
        sign_offs = [
            body_line.replace(TRAILER_KEY_SIGNED_OFF_BY, '').strip(' ')
            for body_line in commit_body
            if body_line.startswith(TRAILER_KEY_SIGNED_OFF_BY)
        ]

        # Check that there is at least one sign off right away
        if len(sign_offs) == 0:
            infractions[commit_sha].append('no sign offs found')
            continue

        # Extract sign off information
        sign_offs_name_email: List[Tuple[str, str]] = []
        for sign_off in sign_offs:
            name, email = extract_name_and_email(sign_off)
            verbose_print('name, email:', name, email)
            if not is_valid_email(email):
                infractions[commit_sha].append(f'invalid email: {email}')
            else:
                sign_offs_name_email.append((name, email))
        
        # Check that author is in the sign offs
        if not author_result in sign_offs_name_email:
            infractions[commit_sha].append(
                f'sign off not found for commit author: {commit_author_data} (found: {sign_offs})')

    # Check failed if there are any infractions
    if len(infractions) > 0:
        print('INFRACTIONS')
        for commit_sha, commit_infractions in infractions.items():
            print(f'commit {commit_sha}:')
            for commit_infraction in commit_infractions:
                print(f'\t{commit_infraction}')
        return 1
    if len(individual_commits) == 0:
        print('warning: no commits were actually checked')
    print('Good')
    return 0


if __name__ == '__main__':
    sys.exit(main())
