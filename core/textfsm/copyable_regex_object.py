#!/usr/bin/python
#
# Copyright 2012 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied. See the License for the specific language governing
# permissions and limitations under the License.

"""Work around a regression in Python 2.6 that makes RegexObjects uncopyable."""


import re
from builtins import object    # pylint: disable=redefined-builtin


class CopyableRegexObject(object):
  """Like a re.RegexObject, but can be copied."""

  def __init__(self, pattern):
    self.pattern = pattern
    self.regex = re.compile(pattern)

  def match(self, *args, **kwargs):
    return self.regex.match(*args, **kwargs)

  def sub(self, *args, **kwargs):
    return self.regex.sub(*args, **kwargs)

  def __copy__(self):
    return CopyableRegexObject(self.pattern)

  def __deepcopy__(self, unused_memo):
    return self.__copy__()
