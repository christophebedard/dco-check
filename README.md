# dco-check

[![PyPI](https://img.shields.io/pypi/v/dco-check)](https://pypi.org/project/dco-check/)
[![codecov](https://codecov.io/gh/christophebedard/dco-check/branch/master/graph/badge.svg)](https://codecov.io/gh/christophebedard/dco-check)
[![License](https://img.shields.io/github/license/christophebedard/dco-check)](https://github.com/christophebedard/dco-check/blob/master/LICENSE)
[![Docker Pulls](https://img.shields.io/docker/pulls/christophebedard/dco-check?logo=docker)](https://hub.docker.com/r/christophebedard/dco-check)

[![GitHub Action Status](https://img.shields.io/github/workflow/status/christophebedard/dco-check/CI?label=CI&logo=github)](https://github.com/christophebedard/dco-check)
[![GitLab pipeline status](https://img.shields.io/gitlab/pipeline/christophebedard/dco-check?label=CI&logo=gitlab)](https://gitlab.com/christophebedard/dco-check/commits/master)
[![Travis CI](https://img.shields.io/travis/com/christophebedard/dco-check?label=CI&logo=travis)](https://travis-ci.com/github/christophebedard/dco-check)
[![Azure DevOps builds](https://img.shields.io/azure-devops/build/christophebedard/74e64a5d-0fe6-4759-bb97-eb77bb0d15af/1?label=CI&logo=azure%20pipelines)](https://dev.azure.com/christophebedard/dco-check/_build/latest?definitionId=1&branchName=master)
[![AppVeyor](https://img.shields.io/appveyor/build/christophebedard/dco-check?label=CI&logo=appveyor)](https://ci.appveyor.com/project/christophebedard/dco-check)
[![CircleCI](https://img.shields.io/circleci/build/github/christophebedard/dco-check?label=CI&logo=circle&logoColor=white)](https://circleci.com/gh/christophebedard/dco-check)

Simple DCO check script to be used in [any CI](#ci-support).

## Motivation

Many open-source projects require the use of a `Signed-off-by:` line in every commit message.
This is to certify that a contributor has the right to submit their code according to the [Developer Certificate of Origin (DCO)](https://developercertificate.org/).
However, to my knowledge, there is no automated check that can run on any CI platform (or most platforms).
Some platforms simply do not possess such a feature.

This was inspired by the [DCO GitHub App](https://github.com/apps/dco).

## How to get & use

There are a few options:

1. Using the [package from PyPI](https://pypi.org/project/dco-check/)
    ```shell
    $ pip install dco-check
    $ dco-check
    ```
1. Using the Docker image ([`christophebedard/dco-check`](https://hub.docker.com/r/christophebedard/dco-check)) with your CI (see [examples](#Example-CI-configurations))
    ```shell
    $ dco-check
    ```
1. Downloading the script and running it (you can replace `master` with a specific version)  
    This is enabled by the fact that `dco-check` is a single Python file without any third-party dependencies.
    ```shell
    $ wget https://raw.githubusercontent.com/christophebedard/dco-check/master/dco_check/dco_check.py
    $ python3 dco_check.py
    ```

It exits with 0 if all checked commits have been signed-off.
Otherwise, it exits with a non-zero number.

Run with `--help` for more information and options, including:

* ignoring merge commits
* default branch
* default remote
* quiet mode
* verbose mode

Those options can alternatively be set through environment variables (see `--help`), but commandline arguments always have precedence over environment variables.

## How it works

`dco-check` focuses on two use-cases:

1. Commits part of a feature branch, i.e. a proposed change (pull request or merge request)
1. Commits on the default branch, e.g. `master`, or more specifically the new commits pushed to the default branch

The first use-case is easy to cover given a normal git repository.
We can simply use `git merge-base --fork-point $DEFAULT_BRANCH` to get the list of commits on a specific feature branch off of the default branch.
Some CIs provide even more information, such as the target branch of the change, which is useful if we don't expect to always target the default branch.
Then we can just check every commit using `git log` and make sure it is signed-off by the author.

The second use-case isn't really possible with simple git repositories, because they do not contain the necessary information (AFAIK).
Fortunately, some CIs do provide this information.

Furthermore, by default, some CI platforms only clone git repositories up to a specific depth, i.e. you only get a partial commit history.
This depth can sometimes be 1 for some CIs, i.e. a shallow clone.
For those cases, it is usually possible to prevent shallow cloning by setting the right parameter(s) in the job configuration.
However, since one of the goals of `dco-check` is to be as easy to use as possible, it tries not to rely on that.

This is why `dco-check` detects the current CI platform and uses whatever information that platform can provide.
Otherwise, it falls back on a default generic implementation which uses simple git commands.
In those cases, the CLI options allow users to provide a lot of the missing information.

## CI support

Below is a summary of the supported CIs along with their known behaviours.

| CI | Detects new changes when pushing to default branch | Detects PRs/MRs | Gets base branch using | Gets default branch using | Notes |
|:--:|:--------------------------------------------------:|:---------------:|:----------------------:|:-------------------------:|:-----:|
|GitHub|✓|✓|CI|(not used)|retrieves commit data using the GitHub API, since GitHub does shallow clones by default|
|GitLab|✓|✓|CI|CI|detects normal GitLab MRs and external (GitHub) MRs|
|Azure Pipelines||✓|CI|CLI arguments||
|AppVeyor||✓|CI|CLI arguments||
|CircleCI|✓||CI\* (or CLI arguments)|CLI arguments|\*can use base revision information if provided (see example)|
|Travis CI|||CLI arguments|CLI arguments|supported by default as a normal git repo|
|default (git)|||CLI arguments|CLI arguments|use locally; using in an unsupported CI which only does a shallow clone might cause problems|

## Example CI configurations

Here are some example CI configurations.

### GitHub

```yaml
# .github/workflows/dco.yml
name: DCO
on:
  pull_request:
  push:
    branches:
      - master
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v1
      with:
        python-version: 3.8
    - name: Check DCO
      env:
        GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      run: |
        pip3 install -U dco-check
        dco-check
```

### GitLab

```yaml
# .gitlab-ci.yml
variables:
  DOCKER_DRIVER: overlay2
dco:
  image: christophebedard/dco-check:latest
  rules:
    - if: $CI_MERGE_REQUEST_ID
    - if: $CI_EXTERNAL_PULL_REQUEST_IID
    - if: $CI_COMMIT_BRANCH == 'master'
  script:
    - pip3 install -U dco-check  # optional
    - dco-check
```

## Python version support

Python 3.6+ is required because of the use of f-strings.
However, it shouldn't be too hard to remove them to support older versions of Python 3, if there is a demand for it, or if such a change is contributed to `dco-check`.

## Contributing

See [`CONTRIBUTING.md`](./CONTRIBUTING.md).
