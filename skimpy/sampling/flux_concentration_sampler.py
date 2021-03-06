# -*- coding: utf-8 -*-
"""
.. module:: skimpy
   :platform: Unix, Windows
   :synopsis: Simple Kinetic Models in Python

.. moduleauthor:: SKiMPy team

[---------]

Copyright 2019 Laboratory of Computational Systems Biotechnology (LCSB),
Ecole Polytechnique Federale de Lausanne (EPFL), Switzerland

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIE CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

"""

from abc import ABC, abstractmethod
from collections import namedtuple

import numpy as np
from numpy.random import sample
#from scipy.sparse.linalg import eigs as eigenvalues
from scipy.linalg import eigvals as eigenvalues
from sympy import sympify, Symbol

from skimpy.utils.namespace import *

from .saturation_parameter_function import SaturationParameterFunction
from .flux_parameter_function import  FluxParameterFunction

class FluxConcentrationSampler(ABC):
    def __init__(self, parameters=None):
        """

        :param parameters:
        """
        self.parameters = parameters

    @property
    @abstractmethod
    def Parameters(self):
        """
        Parameter type specified for the parameters sampling procedure
        :return:
        """

    @abstractmethod
    def sample(self):
        """

        :return:
        """


