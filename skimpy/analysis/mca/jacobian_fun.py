# -*- coding: utf-8 -*-
"""
.. module:: skimpy
   :platform: Unix, Windows
   :synopsis: Simple Kinetic Models in Python

.. moduleauthor:: SKiMPy team

[---------]

Copyright 2017 Laboratory of Computational Systems Biotechnology (LCSB),
Ecole Polytechnique Federale de Lausanne (EPFL), Switzerland

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

"""

from numpy import array

from scipy.sparse import diags
from scipy.sparse.linalg import inv as sparse_inv


class JacobianFunction:
    def __init__(self,
                 reduced_stoichometry,
                 independent_elasticity_function,
                 dependent_elasticity_function,
                 conservation_relation,
                 independent_variable_ix,
                 dependent_variable_ix,
                 ):

        self.reduced_stoichometry = reduced_stoichometry
        self.dependent_elasticity_function  = dependent_elasticity_function
        self.independent_elasticity_function = independent_elasticity_function
        self.independent_variable_ix = independent_variable_ix
        self.dependent_variable_ix = dependent_variable_ix
        self.conservation_relation = conservation_relation

    def __call__(self, fluxes, concentrations, parameters):
        """
        :param fluxes: `Dict` or `pd.Series` of reference flux vector
        :param concentrations: `Dict` or `pd.Series` of reference concentration vector
        :param parameters: `Dict` or `pd.Series` of reference parameters vector
        """

        #Calculate the Jacobian
        flux_matrix = diags(array(fluxes), 0).tocsc()

        # Elasticity matrix
        if self.conservation_relation.nnz == 0:
            concentration_matrix = diags(array(concentrations)).tocsc()
            inv_concentration_matrix = sparse_inv(concentration_matrix)
            elasticity_matrix = self.independent_elasticity_function(concentrations,parameters)
        else:
            # We need to get only the concentrations of the independent metabolites
            ix = self.independent_variable_ix
            concentration_matrix = diags(array(concentrations)[ix]).tocsc()
            inv_concentration_matrix = sparse_inv(concentration_matrix)

            elasticity_matrix = self.independent_elasticity_function(concentrations, parameters)

            dependent_weights = self.dependent_elasticity_function.\
                get_dependent_weights(
                                concentration_vector=concentrations,
                                L0=self.conservation_relation,
                                all_dependent_ix=self.dependent_variable_ix,
                                all_independent_ix=self.independent_variable_ix,
                            )

            elasticity_matrix += self.dependent_elasticity_function(concentrations, parameters)\
                                 .dot(dependent_weights)

        jacobian = self.reduced_stoichometry.dot(flux_matrix)\
                    .dot(elasticity_matrix)\
                    .dot(inv_concentration_matrix)

        return jacobian
