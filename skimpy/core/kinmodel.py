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

from scikits.odes import ode
from skimpy.analysis.ode.utils import make_ode_fun
from skimpy.analysis.mca.utils import make_mca_functions
from skimpy.analysis.mca.jacobian_fun import JacobianFunction
from ..utils.logger import get_bistream_logger
from .solution import ODESolution

from ..utils import TabDict, iterable_to_tabdict
from ..utils.namespace import *


class KineticModel(object):
    """
    This class contains the kinetic model as described by reaction and
    boundary conditions and constratins.

    :param :
    :return:
    """

    def __init__(self,
                 reactions=None,
                 boundary_conditions=None,
                 constraints=None,
                 name='Unnamed'):
        self.name = name
        self.reactions = iterable_to_tabdict(reactions)
        self.boundary_conditions = iterable_to_tabdict(boundary_conditions)
        self.constraints = iterable_to_tabdict(constraints)
        self.initial_conditions = iterable_to_tabdict([])
        self.logger = get_bistream_logger(name)
        self._sim_type = None
        self._modified = True

        self.parameters = TabDict()

    # TODO : Implement
    @property
    def metabolites(self):
        pass

    def add_reaction(self, reaction):
        self.add_to_tabdict(reaction, 'reactions')

    def add_constraint(self, constraint):
        constraint.link(self)
        self.add_to_tabdict(constraint, 'constraints')

    def add_boundary_condition(self, boundary_condition):
        boundary_condition.link(self)
        self.add_to_tabdict(boundary_condition, 'boundary_conditions')

    def add_to_tabdict(self, element, kind):

        the_tabdict = getattr(self, kind)

        # Add an enzyme to the model
        if element.name in the_tabdict:
            error_msg = 'Reaction {} already exists in the model'
            raise(Exception(error_msg.format(element.name)))

        the_tabdict[element.name] = element

        # TODO : Implement with metabolites
        # for this_metabolite in reaction.metabolites:
        #     self.metabolites.append(this_metabolite)
        self._modifed = True

    def parametrize(self,param_dict):
        """
        If has input: apply as dict to reactions in the model by
            reaction.parametrize(args)
        :return:
        """
        for reaction_name, the_params in param_dict.items():
            the_reaction = self.reactions[reaction_name]
            the_reaction.parametrize(the_params)

        self.update()

    def update(self):
        for r in self.reactions.values():
            reaction_params = TabDict({str(p.symbol): p for p in r.parameters.values()})
            self.parameters.update(reaction_params)

    @property
    def sim_type(self):
        return self._simtype

    @sim_type.setter
    def sim_type(self, value):
        self._simtype = value
        self._modified = True

    def compile_ode(self,
                    sim_type=QSSA,):

        self.sim_type = sim_type

        # Recompile only if modified or simulation
        if self._modified or self.sim_type != sim_type:
            # Compile ode function
            ode_fun, variables = make_ode_fun(self, sim_type)
            # TODO define the init properly
            self.ode_fun = ode_fun
            self.variables = variables

            self._modified = False
            # Create initial_conditions from variables
            self.initial_conditions = TabDict([(x,0.0) for x in self.variables])

    def solve_ode(self,
                  time_out,
                  solver_type='cvode',
                  **kwargs):
        extra_options = {'old_api': False}
        kwargs.update(extra_options)
        # Choose a solver
        if not hasattr(self, 'solver'):
            self.solver = ode(solver_type, self.ode_fun, **kwargs)

        # Order the initial conditions according to variables
        ordered_initial_conditions = [self.initial_conditions[variable]
                                    for variable in self.variables]

        #if parameters are empty try to fetch from model
        if not self.ode_fun._parameter_values:
            self.ode_fun.parameter_values = {v.symbol:v.value
                                             for k,v in self.parameters.items()}

        # solve the ode
        solution = self.solver.solve(time_out, ordered_initial_conditions)

        return ODESolution(self, solution)

    def compile_mca(self, parameter_list=[], sim_type=QSSA):
            """
            Compile MCA expressions: elasticities, jacobian
            and control coeffcients
            """

            # Recompile only if modified or simulation
            if self._modified or self.sim_type != sim_type:

                # Get the model expressions
                reduced_stoichometriy,\
                independent_elasticity_fun, \
                dependent_elasticity_fun, \
                parameter_elasticities_fun, \
                conservation_relation, \
                all_variables, \
                independent_variables_ix,\
                dependent_variables_ix,\
                    = make_mca_functions(self,
                                                     parameter_list,
                                                     sim_type=sim_type)

                self.independent_elasticity_fun = independent_elasticity_fun
                self.dependent_elasticity_fun = dependent_elasticity_fun
                self.dependent_variables_ix = dependent_variables_ix
                self.independent_variables_ix = independent_variables_ix
                self.parameter_elasticities_fun = parameter_elasticities_fun
                self.conservation_relation = conservation_relation
                self.variables = all_variables
                self.reduced_stoichiometry = reduced_stoichometriy

                self.jacobian_fun = JacobianFunction(reduced_stoichometriy,
                                                     independent_elasticity_fun,
                                                     dependent_elasticity_fun,
                                                     conservation_relation,
                                                     independent_variables_ix,
                                                     dependent_variables_ix)

