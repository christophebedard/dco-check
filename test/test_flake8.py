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
from pathlib import Path

from flake8.api import legacy as flake8


def test_flake8():
    style_guide = flake8.get_style_guide(
        ignore=['D104'],
        show_source=True,
    )
    # Make sure to only check the source
    report = style_guide.check_files([
        os.path.join(str(Path(__file__).parents[1]), 'dco_check'),
    ])

    assert not report.total_errors, f'flake8 found {report.total_errors} errors'
