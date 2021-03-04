# Copyright 2021 Christophe Bedard
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
import sys

from mypy import api


def test_mypy():
    # Make sure to only check the source
    source_dir = os.path.join(str(Path(__file__).parents[1]), 'dco_check')
    normal_report, error_report, exit_status = api.run([source_dir, "--strict"])

    if normal_report:
        print(normal_report)
    if error_report:
        print(error_report, file=sys.stderr)

    assert 0 == exit_status, 'mypy found errors'
