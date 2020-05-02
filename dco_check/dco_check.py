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
import http.client
import json
import os
import re
import subprocess
import sys
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple
from typing import Union


__version__ = '0.0.3'


DEFAULT_BRANCH = 'master'
DEFAULT_REMOTE = 'origin'
TRAILER_KEY_SIGNED_OFF_BY = 'Signed-off-by:'


class BooleanDefaultValue:
    """Default value wrapper for bool."""

    def __init__(self, value):  # noqa: D107
        assert(isinstance(value, bool))
        self._value = value

    def __bool__(self):  # noqa: D105
        return self._value


class StringDefaultValue(str):
    """Default value wrapper for str."""

    pass


_types = {
    bool: BooleanDefaultValue,
    str: StringDefaultValue,
}


def wrap_default_value(
    value: Union[bool, str],
) -> Union[BooleanDefaultValue, StringDefaultValue, Any]:
    """Wrap a default value so that we can check if a value is still the default."""
    # Inspired by: https://github.com/colcon/colcon-core/pull/288/files
    global _types
    if is_default_value(value):
        raise ValueError('tried to wrap a default value a second time')
    if type(value) in _types:
        return _types[type(value)](value)
    return value


def is_default_value(value: Any) -> bool:
    """Check if a value is a default value."""
    global _types
    return isinstance(value, tuple(_types.values()))


def get_parser() -> argparse.ArgumentParser:
    """Get argument parser."""
    parser = argparse.ArgumentParser(
        description='Check that all commits of a proposed change have a DCO, i.e. are signed-off.',
    )
    parser.add_argument(
        '-b', '--default-branch',
        default=wrap_default_value(DEFAULT_BRANCH),
        help='default branch to use, if necessary (default: %(default)s)',
    )
    parser.add_argument(
        '-m', '--check-merge-commits',
        action='store_true',
        default=wrap_default_value(False),
        help='check sign-offs on merge commits as well',
    )
    parser.add_argument(
        '-r', '--default-remote',
        default=wrap_default_value(DEFAULT_REMOTE),
        help='default remote to use, if necessary (default: %(default)s)',
    )
    output_options_group = parser.add_mutually_exclusive_group()
    output_options_group.add_argument(
        '-q', '--quiet',
        action='store_true',
        default=wrap_default_value(False),
        help='quiet mode (do not print anything; simply exit with 0 or non-zero)',
    )
    output_options_group.add_argument(
        '-v', '--verbose',
        action='store_true',
        default=wrap_default_value(False),
        help='verbose mode (print out more information)',
    )
    return parser


def parse_args() -> argparse.Namespace:
    """Parse arguments."""
    return get_parser().parse_args()


class Options:
    """Simple container and utilities for options."""

    def __init__(self, parser: argparse.ArgumentParser) -> None:
        """Create using default argument values."""
        self.check_merge_commits = parser.get_default('m')
        self.default_branch = parser.get_default('b')
        self.default_remote = parser.get_default('r')
        self.quiet = parser.get_default('q')
        self.verbose = parser.get_default('v')

    def set_options(self, args: argparse.Namespace) -> None:
        """Set options using parsed arguments."""
        self.check_merge_commits = args.check_merge_commits
        self.default_branch = args.default_branch
        self.default_remote = args.default_remote
        self.quiet = args.quiet
        self.verbose = args.verbose

    def apply_env_vars(self) -> None:
        """
        Apply environment variable values.

        Only uses an environment variable value if the argument has not been set through CLI.
        """
        def real_cast(value: Any, param_type: Any) -> Any:
            """Because bool('False') is True."""
            if param_type is bool:
                return value in [1, '1', 'true', 'True', 'y', 'Y', 'yes', 'Yes']
            return param_type(value)

        def environment_value_if_default_param(
            param_name: str,
            param_type: Any,
            env_var_name: str,
        ) -> Optional[Any]:
            """
            Choose value between environment variable and CLI argument.

            Returns environment variable value if it exists and the parameter has a default value.
            """
            if not hasattr(self, param_name):
                raise ValueError('parameter name does not exist')
            value = getattr(self, param_name)
            # Use environment variable value if it exists, otherwise keep default value
            if is_default_value(value):
                return real_cast(
                    get_env_var(env_var_name, print_if_not_found=False, default=value),
                    param_type,
                )
            else:
                return real_cast(value, param_type)
        self.check_merge_commits = environment_value_if_default_param(
            'check_merge_commits',
            bool,
            'DCO_CHECK_CHECK_MERGE_COMMITS',
        )
        self.default_branch = environment_value_if_default_param(
            'default_branch',
            str,
            'DCO_CHECK_DEFAULT_BRANCH',
        )
        self.default_remote = environment_value_if_default_param(
            'default_remote',
            str,
            'DCO_CHECK_DEFAULT_REMOTE',
        )
        self.quiet = environment_value_if_default_param('quiet', bool, 'DCO_CHECK_QUIET')
        self.verbose = environment_value_if_default_param('verbose', bool, 'DCO_CHECK_VERBOSE')
        if self.quiet and self.verbose:
            raise ValueError("'quiet' and 'verbose' cannot both be true")


options = Options(get_parser())


class Logger:
    """Simple logger to stdout which can be quiet or verbose."""

    def __init__(self, parser: argparse.ArgumentParser) -> None:
        """Create using default argument values."""
        self.__quiet = parser.get_default('q')
        self.__verbose = parser.get_default('v')

    def set_options(self, options: Options) -> None:
        """Set options using options object."""
        self.__quiet = options.quiet
        self.__verbose = options.verbose

    def print(self, msg='', *args, **kwargs) -> None:  # noqa: A003
        """Print if not quiet."""
        if not self.__quiet:
            print(msg, *args, **kwargs)

    def verbose_print(self, msg='', *args, **kwargs) -> None:
        """Print if verbose."""
        if self.__verbose:
            print(msg, *args, **kwargs)


logger = Logger(get_parser())


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
            logger.print(f'error: {output_stdout.decode("utf8")}')
        else:
            output = output_stdout.rstrip().decode('utf8').strip('\n')
    except subprocess.CalledProcessError as e:
        logger.print(f'error: {e.output.decode("utf8")}')
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


def fetch_branch(
    branch: str,
    remote: str = 'origin',
) -> int:
    """
    Fetch branch from remote.

    See: git fetch

    :param branch: the name of the branch
    :param remote: the name of the remote
    :return: zero for success, nonzero otherwise
    """
    command = [
        'git',
        'fetch',
        remote,
        branch,
    ]
    # We don't want the output
    return 0 if run(command) is not None else 1


def get_commits_data(
    base: str,
    head: str,
    ignore_merge_commits: bool = True,
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
    :param ignore_merge_commits: whether to ignore merge commits
    :return: the data, or `None` if it failed
    """
    command = [
        'git',
        'log',
        f'{base}..{head}',
        '--pretty=%H%n%an <%ae>%n%s%n%-b%x1e',
    ]
    if ignore_merge_commits:
        command += ['--no-merges']
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
    individual_commits = [
        single_output.strip('\n') for single_output in commits_data.split(commits_sep)
    ]
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
                logger.print(
                    f"could not get environment variable: '{env_var}'; "
                    f"using value default value: '{default}'"
                )
            value = default
        elif print_if_not_found:
            logger.print(f"could not get environment variable: '{env_var}'")
    return value


class CommitInfo:
    """Container for all necessary commit information."""

    def __init__(
        self,
        commit_hash: str,
        title: str,
        body: List[str],
        author_name: str,
        author_email: str,
        is_merge_commit: bool = False,
    ) -> None:
        """Create a CommitInfo object."""
        self.hash = commit_hash
        self.title = title
        self.body = body
        self.author_name = author_name
        self.author_email = author_email
        self.is_merge_commit = is_merge_commit

    def __repr__(self) -> str:  # noqa: D105
        s = (
            f'hash: {self.hash}\ntitle: {self.title}\nbody: {self.body}\n'
            f'author: {self.author_name} <{self.author_email}>'
        )
        if self.is_merge_commit:
            s += '\n(merge commit)'
        return s


class CommitDataRetriever:
    """
    Abstract commit data retriever.

    It first provides a method to check whether it applies to the current setup or not.
    It also provides other methods to get commits to be checked.
    These should not be called if it doesn't apply.
    """

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

    def get_commits(self, base: str, head: str, **kwargs) -> Optional[List[CommitInfo]]:
        """Get commit data."""
        raise NotImplementedError


class GitRetriever(CommitDataRetriever):
    """Implementation for any git repository."""

    def name(self) -> str:
        """Get a name that represents this retriever."""
        return 'git (default)'

    def applies(self) -> bool:
        """Check if this retriever applies, i.e. can provide commit data."""
        # Unless we only have access to a partial commit history
        return True

    def get_commit_range(self) -> Optional[Tuple[str, str]]:
        """
        Get the range of commits to be checked: (last commit that was checked, latest commit).

        The range excludes the first commit, e.g. ]first commit, second commit]

        :return the (last commit that was checked, latest commit) tuple, or `None` if it failed
        """
        commit_hash_base = get_common_ancestor_commit_hash(options.default_branch)
        if commit_hash_base is None:
            return None
        commit_hash_head = get_head_commit_hash()
        if commit_hash_head is None:
            return None
        return commit_hash_base, commit_hash_head

    def get_commits(
        self,
        base: str,
        head: str,
        check_merge_commits: bool = False,
        **kwargs,
    ) -> Optional[List[CommitInfo]]:
        """Get commit data."""
        ignore_merge_commits = not check_merge_commits
        commits_data = get_commits_data(base, head, ignore_merge_commits=ignore_merge_commits)
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
            # There won't be any merge commits at this point
            is_merge_commit = False
            commits.append(
                CommitInfo(
                    commit_hash,
                    commit_title,
                    commit_body,
                    author_name,
                    author_email,
                    is_merge_commit
                )
            )
        return commits


class GitlabRetriever(CommitDataRetriever):
    """Implementation for GitLab CI."""

    def name(self) -> str:
        """Get a name that represents this retriever."""
        return 'GitLab'

    def applies(self) -> bool:
        """Check if this retriever applies, i.e. can provide commit data."""
        return get_env_var('GITLAB_CI', print_if_not_found=False) is not None

    def get_commit_range(self) -> Optional[Tuple[str, str]]:
        """
        Get the range of commits to be checked: (last commit that was checked, latest commit).

        The range excludes the first commit, e.g. ]first commit, second commit]

        :return the (last commit that was checked, latest commit) tuple, or `None` if it failed
        """
        # See: https://docs.gitlab.com/ee/ci/variables/predefined_variables.html
        default_branch = get_env_var('CI_DEFAULT_BRANCH', default=options.default_branch)

        commit_hash_head = get_env_var('CI_COMMIT_SHA')
        if commit_hash_head is None:
            return None

        # If we're on the default branch, just test new commits
        current_branch = get_env_var('CI_COMMIT_BRANCH')
        if current_branch is not None and current_branch == default_branch:
            logger.verbose_print(
                f"\ton default branch '{current_branch}': "
                'will check new commits'
            )
            commit_hash_base = get_env_var('CI_COMMIT_BEFORE_SHA')
            if commit_hash_base is None:
                return None
            return commit_hash_base, commit_hash_head
        else:
            # Otherwise test all commits off of the default branch
            logger.verbose_print(
                f"\ton branch '{current_branch}': "
                f"will check forked commits off of default branch '{default_branch}'"
            )
            # Fetch default branch
            remote = options.default_remote
            if 0 != fetch_branch(default_branch, remote):
                logger.print(f"failed to fetch '{default_branch}' from remote '{remote}'")
                return None
            # Use remote default branch ref
            remote_branch_ref = remote + '/' + default_branch
            commit_hash_base = get_common_ancestor_commit_hash(remote_branch_ref)
            if commit_hash_base is None:
                return None
            return commit_hash_base, commit_hash_head

    def get_commits(self, base: str, head: str, **kwargs) -> Optional[List[CommitInfo]]:
        """Get commit data."""
        return GitRetriever().get_commits(base, head, **kwargs)


class CircleRetriever(CommitDataRetriever):
    """Implementation for CircleCI."""

    def name(self) -> str:
        """Get a name that represents this retriever."""
        return 'CircleCI'

    def applies(self) -> bool:
        """Check if this retriever applies, i.e. can provide commit data."""
        return get_env_var('CIRCLECI', print_if_not_found=False) is not None

    def get_commit_range(self) -> Optional[Tuple[str, str]]:
        """
        Get the range of commits to be checked: (last commit that was checked, latest commit).

        The range excludes the first commit, e.g. ]first commit, second commit]

        :return the (last commit that was checked, latest commit) tuple, or `None` if it failed
        """
        # See: https://circleci.com/docs/2.0/env-vars/#built-in-environment-variables
        # TODO replace
        default_branch = options.default_branch

        commit_hash_head = get_env_var('CIRCLE_SHA1')
        if commit_hash_head is None:
            return None

        # TODO support testing only new commits on the default branch
        current_branch = get_env_var('CIRCLE_BRANCH')

        # Test all commits off of the default branch
        logger.verbose_print(
            f"\ton branch '{current_branch}': "
            f"will check forked commits off of default branch '{default_branch}'"
        )
        # Fetch default branch
        remote = options.default_remote
        if 0 != fetch_branch(default_branch, remote):
            logger.print(f"failed to fetch '{default_branch}' from remote '{remote}'")
            return None
        # Use remote default branch ref
        remote_branch_ref = remote + '/' + default_branch
        commit_hash_base = get_common_ancestor_commit_hash(remote_branch_ref)
        if commit_hash_base is None:
            return None
        return commit_hash_base, commit_hash_head

    def get_commits(self, base: str, head: str, **kwargs) -> Optional[List[CommitInfo]]:
        """Get commit data."""
        return GitRetriever().get_commits(base, head, **kwargs)


class AzurePipelinesRetriever(CommitDataRetriever):
    """Implementation for Azure Pipelines."""

    def name(self) -> str:
        """Get a name that represents this retriever."""
        return 'Azure Pipelines'

    def applies(self) -> bool:
        """Check if this retriever applies, i.e. can provide commit data."""
        return get_env_var('TF_BUILD', print_if_not_found=False) is not None

    def get_commit_range(self) -> Optional[Tuple[str, str]]:
        """
        Get the range of commits to be checked: (last commit that was checked, latest commit).

        The range excludes the first commit, e.g. ]first commit, second commit]

        :return the (last commit that was checked, latest commit) tuple, or `None` if it failed
        """
        # See: https://docs.microsoft.com/en-us/azure/devops/pipelines/build/variables?view=azure-devops&tabs=yaml#build-variables  # noqa: E501
        # TODO replace
        default_branch = options.default_branch

        commit_hash_head = get_env_var('BUILD_SOURCEVERSION')
        if commit_hash_head is None:
            return None

        # TODO support testing only new commits on the default branch
        current_branch = get_env_var('BUILD_SOURCEBRANCHNAME')

        # TODO use 'System.PullRequest.TargetBranch' and 'System.PullRequest.PullRequestId'

        # Test all commits off of the default branch
        logger.verbose_print(
            f"\ton branch '{current_branch}': "
            f"will check forked commits off of default branch '{default_branch}'"
        )
        # Fetch default branch
        remote = options.default_remote
        if 0 != fetch_branch(default_branch, remote):
            logger.print(f"failed to fetch '{default_branch}' from remote '{remote}'")
            return None
        # Use remote default branch ref
        remote_branch_ref = remote + '/' + default_branch
        commit_hash_base = get_common_ancestor_commit_hash(remote_branch_ref)
        if commit_hash_base is None:
            return None
        return commit_hash_base, commit_hash_head

    def get_commits(self, base: str, head: str, **kwargs) -> Optional[List[CommitInfo]]:
        """Get commit data."""
        return GitRetriever().get_commits(base, head, **kwargs)


class AppVeyorRetriever(CommitDataRetriever):
    """Implementation for AppVeyor."""

    def name(self) -> str:
        """Get a name that represents this retriever."""
        return 'AppVeyor'

    def applies(self) -> bool:
        """Check if this retriever applies, i.e. can provide commit data."""
        return get_env_var('APPVEYOR', print_if_not_found=False) is not None

    def get_commit_range(self) -> Optional[Tuple[str, str]]:
        """
        Get the range of commits to be checked: (last commit that was checked, latest commit).

        The range excludes the first commit, e.g. ]first commit, second commit]

        :return the (last commit that was checked, latest commit) tuple, or `None` if it failed
        """
        # See: https://www.appveyor.com/docs/environment-variables/
        # TODO review this
        default_branch = options.default_branch

        commit_hash_head = get_env_var('APPVEYOR_PULL_REQUEST_HEAD_COMMIT')
        if commit_hash_head is None:
            commit_hash_head = get_head_commit_hash()

        # If we're on the default branch, just test new commits
        current_branch = get_env_var('APPVEYOR_PULL_REQUEST_HEAD_REPO_BRANCH')
        if current_branch is not None and current_branch == default_branch:
            logger.verbose_print(
                f"\ton default branch '{current_branch}': will check new commits"
            )
            commit_hash_base = get_env_var('CI_COMMIT_BEFORE_SHA')
            if commit_hash_base is None:
                return None
            return commit_hash_base, commit_hash_head
        else:
            # Otherwise test all commits off of the default branch
            logger.verbose_print(
                f"\ton branch '{current_branch}': "
                f"will check forked commits off of default branch '{default_branch}'"
            )
            # Fetch default branch
            remote = options.default_remote
            if 0 != fetch_branch(default_branch, remote):
                logger.print(f"failed to fetch '{default_branch}' from remote '{remote}'")
                return None
            # Use remote default branch ref
            remote_branch_ref = remote + '/' + default_branch
            commit_hash_base = get_common_ancestor_commit_hash(remote_branch_ref)
            if commit_hash_base is None:
                return None
            return commit_hash_base, commit_hash_head

    def get_commits(self, base: str, head: str, **kwargs) -> Optional[List[CommitInfo]]:
        """Get commit data."""
        return GitRetriever().get_commits(base, head, **kwargs)


class GitHubRetriever(CommitDataRetriever):
    """Implementation for GitHub CI."""

    def name(self) -> str:
        """Get a name that represents this retriever."""
        return 'GitHub CI'

    def applies(self) -> bool:
        """Check if this retriever applies, i.e. can provide commit data."""
        return get_env_var('GITHUB_ACTIONS', print_if_not_found=False) == 'true'

    def get_commit_range(self) -> Optional[Tuple[str, str]]:
        """
        Get the range of commits to be checked: (last commit that was checked, latest commit).

        The range excludes the first commit, e.g. ]first commit, second commit]

        :return the (last commit that was checked, latest commit) tuple, or `None` if it failed
        """
        # See: https://docs.gitlab.com/ee/ci/variables/predefined_variables.html
        self.github_token = get_env_var('GITHUB_TOKEN')
        if self.github_token is None:
            logger.print('Did you forget to include this in your workflow config?')
            logger.print('\n\tenv:\n\t\tGITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}')
            return None

        # See: https://help.github.com/en/actions/configuring-and-managing-workflows/using-environment-variables  # noqa: E501
        event_payload_path = get_env_var('GITHUB_EVENT_PATH')
        if event_payload_path is None:
            return None
        f = open(event_payload_path)
        self.event_payload = json.load(f)
        f.close()

        # Get base & head commits depending on the workflow event type
        event_name = get_env_var('GITHUB_EVENT_NAME')
        if event_name is None:
            return None
        commit_hash_base = None
        commit_hash_head = None
        if event_name == 'pull_request':
            # See: https://developer.github.com/v3/activity/events/types/#pullrequestevent
            commit_hash_base = self.event_payload['pull_request']['base']['sha']
            commit_hash_head = self.event_payload['pull_request']['head']['sha']
            commit_branch_base = self.event_payload['pull_request']['base']['ref']
            commit_branch_head = self.event_payload['pull_request']['head']['ref']
            logger.verbose_print(
                f"\ton pull request branch '{commit_branch_head}': "
                f"will check commits off of base branch '{commit_branch_base}'"
            )
        elif event_name == 'push':
            # See: https://developer.github.com/v3/activity/events/types/#pushevent
            created = self.event_payload['created']
            if created:
                # If the branch was just created, there won't be a 'before' commit,
                # therefore just get the first commit in the new branch and append '^'
                # to get the commit before that one
                commits = self.event_payload['commits']
                # TODO check len(commits),
                # it's probably 0 when pushing a new branch that is based on an existing one
                commit_hash_base = commits[0]['id'] + '^'
            else:
                commit_hash_base = self.event_payload['before']
            commit_hash_head = self.event_payload['head_commit']['id']
        else:
            logger.print('Unknown workflow event:', event_name)
            return None
        return commit_hash_base, commit_hash_head

    def get_commits(self, base: str, head: str, **kwargs) -> Optional[List[CommitInfo]]:
        """Get commit data."""
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
            from pprint import pprint
            logger.print('Request failed: compare_url')
            logger.print('reponse:', pprint(response.read().decode()))
            return None

        # Extract data
        response_json = json.load(response)
        commits = []
        for commit in response_json['commits']:
            commit_hash = commit['sha']
            message = commit['commit']['message'].split('\n')
            message = list(filter(None, message))
            commit_title = message[0]
            commit_body = message[1:]
            author_name = commit['commit']['author']['name']
            author_email = commit['commit']['author']['email']
            is_merge_commit = len(commit['parents']) > 1
            commits.append(
                CommitInfo(
                    commit_hash,
                    commit_title,
                    commit_body,
                    author_name,
                    author_email,
                    is_merge_commit,
                )
            )
        return commits


def process_commits(
    commits: List[CommitInfo],
    check_merge_commits: bool,
) -> Dict[str, List[str]]:
    """
    Process commit information to detect DCO infractions.

    :param commits: the list of commit info
    :param check_merge_commits: true to check merge commits, false otherwise
    :return: the infractions as a dict {commit sha, infraction explanation}
    """
    infractions: Dict[str, List[str]] = defaultdict(list)
    for commit in commits:
        # Skip this commit if it is a merge commit and the
        # option for checking merge commits is not enabled
        if commit.is_merge_commit and not check_merge_commits:
            logger.verbose_print('\t' + 'ignoring merge commit:', commit.hash)
            logger.verbose_print()
            continue

        logger.verbose_print(
            '\t' + commit.hash + (' (merge commit)' if commit.is_merge_commit else '')
        )
        logger.verbose_print('\t' + commit.author_name, commit.author_email)
        logger.verbose_print('\t' + commit.title)
        logger.verbose_print('\t' + '\n\t'.join(commit.body))

        # Check author name and email
        if any(d is None for d in [commit.author_name, commit.author_email]):
            infractions[commit.hash].append(
                f'could not extract author data for commit: {commit.hash}'
            )
            continue

        # Extract sign-off data
        sign_offs = [
            body_line.replace(TRAILER_KEY_SIGNED_OFF_BY, '').strip(' ')
            for body_line in commit.body
            if body_line.startswith(TRAILER_KEY_SIGNED_OFF_BY)
        ]

        # Check that there is at least one sign-off right away
        if len(sign_offs) == 0:
            infractions[commit.hash].append('no sign-off found')
            continue

        # Extract sign off information
        sign_offs_name_email: List[Tuple[str, str]] = []
        for sign_off in sign_offs:
            name, email = extract_name_and_email(sign_off)
            logger.verbose_print('\t\t' + 'found sign-off:', name, email)
            if not is_valid_email(email):
                infractions[commit.hash].append(f'invalid email: {email}')
            else:
                sign_offs_name_email.append((name, email))

        # Check that author is in the sign-offs
        if not (commit.author_name, commit.author_email) in sign_offs_name_email:
            infractions[commit.hash].append(
                'sign-off not found for commit author: '
                f'{commit.author_name} {commit.author_email}; found: {sign_offs}'
            )

        # Separator between commits
        logger.verbose_print()

    return infractions


def check_infractions(
    infractions: Dict[str, List[str]],
) -> int:
    """
    Check infractions.

    :param infractions: the infractions dict {commit sha, infraction explanation}
    :return: 0 if no infractions, non-zero otherwise
    """
    if len(infractions) > 0:
        logger.print('Missing sign-off(s):')
        logger.print()
        for commit_sha, commit_infractions in infractions.items():
            logger.print('\t' + commit_sha)
            for commit_infraction in commit_infractions:
                logger.print('\t\t' + commit_infraction)
        return 1
    logger.print('All good!')
    return 0


def main() -> int:
    """
    Entrypoint.

    :return: 0 if successful, non-zero otherwise
    """
    args = parse_args()
    options.set_options(args)
    options.apply_env_vars()
    logger.set_options(options)

    # Detect CI
    # Use first one that applies
    retrievers = [
        GitlabRetriever,
        GitHubRetriever,
        AzurePipelinesRetriever,
        AppVeyorRetriever,
        CircleRetriever,
        GitRetriever,
    ]
    commit_retriever = None
    for retriever_cls in retrievers:
        retriever = retriever_cls()
        if retriever.applies():
            commit_retriever = retriever
            break
    logger.print('Detected:', commit_retriever.name())

    # Get range of commits
    commit_range = commit_retriever.get_commit_range()
    if commit_range is None:
        return 1
    commit_hash_base, commit_hash_head = commit_range

    logger.print()
    # Return success now if base == head
    if commit_hash_base == commit_hash_head:
        logger.print('No commits to check')
        return 0

    logger.print(f'Checking commits: {commit_hash_base}..{commit_hash_head}')
    logger.print()

    # Get commits
    commits = commit_retriever.get_commits(
        commit_hash_base,
        commit_hash_head,
        check_merge_commits=options.check_merge_commits,
    )
    if commits is None:
        return 1

    # Process them
    infractions = process_commits(commits, options.check_merge_commits)

    # Check if there are any infractions
    result = check_infractions(infractions)

    if len(commits) == 0:
        logger.print('Warning: no commits were actually checked')

    return result


if __name__ == '__main__':
    sys.exit(main())
