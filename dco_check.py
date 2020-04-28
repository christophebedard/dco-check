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


def run(
    command: List[str],
) -> Optional[str]:
    """
    Run command.

    :param command: the command list
    :return: the stdout output if the return code is 0, otherwise `None`
    """
    output = None
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        output_stdout, _ = process.communicate()
        if process.returncode != 0:
            print(f'error: {output_stdout.decode("utf8")}')
        else:
            output = output_stdout.rstrip().decode('utf8').strip('\n')
    except subprocess.CalledProcessError as e:
        print(f'error: {e.output.decode("utf8")}')
    return output


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


def get_head_commit_hash() -> Optional[str]:
    """
    Get the hash of the HEAD commit.

    :return: the hash of the HEAD commit, or `None` if it failed
    """
    command = [
        'git',
        'rev-parse',
        '--verify',
        'HEAD',
    ]
    return run(command)


def get_common_ancestor_commit_hash(
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
    return run(command)


def get_commits_data(
    base: str,
    head: str,
) -> Optional[str]:
    """
    Get data (full sha & commit body) for commits in a range.

    The range excludes the 'before' commit, e.g. ]base, head]
    The output data contains data for individual commits, separated by special characters:
       * 1st line: full commit sha
       * 2nd line: author name and email
       * 3rd line: commit title (subject)
       * subsequent lines: commit body (which excludes the commit title line)
       * record separator (0x1e)

    :param base: the sha of the commit just before the start of the range
    :param head: the sha of the last commit of the range
    :return: the data, or `None` if it failed
    """
    command = [
        'git',
        'log',
        f'{base}..{head}',
        '--pretty=%H%n%an <%ae>%n%s%n%-b%x1e',
        '--no-merges',
    ]
    return run(command)


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


class CommitInfo:

    def __init__(
        self,
        hash: str,
        title: str,
        body: List[str],
        author_name: str,
        author_email: str,
    ) -> None:
        self.hash = hash
        self.title = title
        self.body = body
        self.author_name = author_name
        self.author_email = author_email

    def __repr__(self) -> str:
        return f'hash: {self.hash}\ntitle: {self.title}\nbody: {self.body}\nauthor: {self.author_name} <{self.author_email}>'


class CommitDataRetriever:

    def name(self) -> str:
        """Get a name that represents this retriever."""
        raise NotImplementedError

    def applies(self) -> bool:
        """Check if this retriever applies, i.e. can provide commit data."""
        raise NotImplementedError

    def get_commit_range(self) -> Optional[Tuple[str, str]]:
        """
        Get the range of commits to be checked: (last commit that was checked, latest commit).

        The range excludes the first commit, e.g. ]first commit, second commit]

        :return the (last commit that was checked, latest commit) tuple, or `None` if it failed
        """
        raise NotImplementedError

    def get_commits(self, base: str, head: str) -> Optional[List[CommitInfo]]:
        """Get commit data."""
        raise NotImplementedError


class GitRetriever(CommitDataRetriever):

    def name(self) -> str:
        return 'Git (default)'

    def applies(self) -> bool:
        # Unless we only have access to a partial commit history
        return True

    def get_commit_range(self) -> Optional[Tuple[str, str]]:
        commit_hash_base = get_common_ancestor_commit_hash(DEFAULT_DEFAULT_BRANCH)
        if commit_hash_base is None:
            return None
        commit_hash_head = get_head_commit_hash()
        if commit_hash_head is None:
            return None
        return commit_hash_base, commit_hash_head

    def get_commits(self, base: str, head: str) -> Optional[List[CommitInfo]]:
        commits_data = get_commits_data(base, head)
        individual_commits = split_commits_data(commits_data)
        commits = []
        for commit_data in individual_commits:
            commit_lines = commit_data.split('\n')
            commit_hash = commit_lines[0]
            commit_author_data = commit_lines[1]
            commit_title = commit_lines[2]
            commit_body = commit_lines[3:]
            author_result = extract_name_and_email(commit_author_data)
            author_name, author_email = None, None
            if author_result is not None:
                author_name, author_email = author_result
            commits.append(CommitInfo(commit_hash, commit_title, commit_body, author_name, author_email))
        return commits


class GitlabRetriever(CommitDataRetriever):

    def name(self) -> str:
        return 'GitLab'

    def applies(self) -> bool:
        return get_env_var('GITLAB_CI', print_if_not_found=False) is not None

    def get_commit_range(self) -> Optional[Tuple[str, str]]:
        # See: https://docs.gitlab.com/ee/ci/variables/predefined_variables.html
        default_branch = get_env_var('CI_DEFAULT_BRANCH', default=DEFAULT_DEFAULT_BRANCH)

        commit_hash_head = get_env_var('CI_COMMIT_SHA')
        if commit_hash_head is None:
            return None

        # If we're on the default branch, just test new commits
        current_branch = get_env_var('CI_COMMIT_BRANCH')
        if current_branch is not None and current_branch == default_branch:
            verbose_print(f'on default branch \'{current_branch}\': will check new commits')
            commit_hash_base = get_env_var('CI_COMMIT_BEFORE_SHA')
            if commit_hash_base is None:
                return None
            return commit_hash_base, commit_hash_head
        else:
            # Otherwise test all commits off of the default branch
            verbose_print(f'on branch \'{current_branch}\': will check forked commits off of default branch \'{default_branch}\'')
            commit_hash_base = get_common_ancestor_commit_hash(default_branch)
            if commit_hash_base is None:
                return None
            return commit_hash_base, commit_hash_head

    def get_commits(self, base: str, head: str) -> Optional[List[CommitInfo]]:
        return GitRetriever().get_commits(base, head)


import http.client
import json
from pprint import pprint
class GitHubRetriever(CommitDataRetriever):

    def name(self) -> str:
        return 'GitHub CI'

    def applies(self) -> bool:
        return get_env_var('GITHUB_ACTIONS', print_if_not_found=False) == 'true'

    def get_commit_range(self) -> Optional[Tuple[str, str]]:
        # See: https://docs.gitlab.com/ee/ci/variables/predefined_variables.html
        verbose_print('GITHUB_EVENT_NAME:', get_env_var('GITHUB_EVENT_NAME'))
        # See: https://help.github.com/en/actions/configuring-and-managing-workflows/using-environment-variables
        event_payload_path = get_env_var('GITHUB_EVENT_PATH')
        if event_payload_path is None:
            return None
        self.github_token = get_env_var('GITHUB_TOKEN')
        if self.github_token is None:
            print('Did you forget to include this in your workflow config?')
            print('\n\tenv:\n\t\tGITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}')
            return None
        f = open(event_payload_path)
        self.event_payload = json.load(f)
        f.close()
        # See: https://developer.github.com/v3/activity/events/types/#pullrequestevent
        commit_hash_base = self.event_payload['pull_request']['base']['sha']
        commit_hash_head = self.event_payload['pull_request']['head']['sha']
        return commit_hash_base, commit_hash_head

    def get_commits(self, base: str, head: str) -> Optional[List[CommitInfo]]:
        # Request commit data
        compare_url_template = self.event_payload['repository']['compare_url']
        compare_url = compare_url_template.format(base=base, head=head)
        connection = http.client.HTTPSConnection('api.github.com')
        headers = {
            'User-Agent': 'dco_check',
            'Authorization': 'token ' + self.github_token,
        }
        connection.request('GET', compare_url, headers=headers)
        response = connection.getresponse()
        if 200 != response.getcode():
            print('Request failed: compare_url')
            print('reponse:', pprint(response.read().decode()))
            return None
        response_json = json.load(response)
        verbose_print('reponse:', pprint(response_json))

        # Extract data
        commits = []
        for commit in response_json['commits']:
            commit_hash = commit['sha']
            message = commit['commit']['message'].split('\n')
            message = list(filter(None, message))
            commit_title = message[0]
            commit_body = message[1:]
            author_name = commit['commit']['author']['name']
            author_email = commit['commit']['author']['email']
            commits.append(CommitInfo(commit_hash, commit_title, commit_body, author_name, author_email))
        return commits


# TODO find a better way to do this
verbose = False
def verbose_print(msg, *args, **kwargs) -> None:
    global verbose
    if verbose:
        print(msg, *args, **kwargs)


def main() -> int:
    args = parse_args()
    global verbose
    verbose = args.verbose

    # Detect CI
    # Use first one that applies
    commit_retriever = None
    for retriever_cls in [GitlabRetriever, GitHubRetriever, GitRetriever]:
        retriever = retriever_cls()
        if retriever.applies():
            commit_retriever = retriever
            break
    print('detected:', commit_retriever.name())

    # Get range of commits
    commit_range = commit_retriever.get_commit_range()
    if commit_range is None:
        return 1
    commit_hash_base, commit_hash_head = commit_range
    verbose_print(f'commit range: {commit_hash_base}..{commit_hash_head}')

    # Get commits
    commits = commit_retriever.get_commits(commit_hash_base, commit_hash_head)
    if commits is None:
        return 1
    verbose_print('commits:', ('\n' + commits.__repr__()).replace('\n', '\n\t'))

    # Process them
    infractions: Dict[str, List[str]] = defaultdict(list)
    for commit in commits:
        verbose_print('commit hash:', commit.hash)
        verbose_print('commit author:', commit.author_name, commit.author_email)
        verbose_print('commit body:', commit.body)

        # Check author name and email
        if any(d is None for d in [commit.author_name, commit.author_email]):
            infractions[commit.hash].append(f'could not extract author data for commit: {commit.hash}')
            continue

        # Extract sign off data
        sign_offs = [
            body_line.replace(TRAILER_KEY_SIGNED_OFF_BY, '').strip(' ')
            for body_line in commit.body
            if body_line.startswith(TRAILER_KEY_SIGNED_OFF_BY)
        ]

        # Check that there is at least one sign off right away
        if len(sign_offs) == 0:
            infractions[commit.hash].append('no sign offs found')
            continue

        # Extract sign off information
        sign_offs_name_email: List[Tuple[str, str]] = []
        for sign_off in sign_offs:
            name, email = extract_name_and_email(sign_off)
            verbose_print('name, email:', name, email)
            if not is_valid_email(email):
                infractions[commit.hash].append(f'invalid email: {email}')
            else:
                sign_offs_name_email.append((name, email))
        
        # Check that author is in the sign offs
        if not (commit.author_name, commit.author_email) in sign_offs_name_email:
            infractions[commit.hash].append(
                f'sign off not found for commit author: {(commit.author_name, commit.author_email)} (found: {sign_offs})')

    # Check failed if there are any infractions
    if len(infractions) > 0:
        print('INFRACTIONS')
        for commit_sha, commit_infractions in infractions.items():
            print(f'commit {commit_sha}:')
            for commit_infraction in commit_infractions:
                print(f'\t{commit_infraction}')
        return 1
    if len(commits) == 0:
        print('warning: no commits were actually checked')
    print('Good')
    return 0


if __name__ == '__main__':
    sys.exit(main())
