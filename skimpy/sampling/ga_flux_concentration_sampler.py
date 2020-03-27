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
WITHOUT WARRANTIE CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

"""
from collections import namedtuple
import numpy as np
#from scipy.sparse.linalg import eigs as eigenvalues
from scipy.linalg import eigvals as eigenvalues
from sympy import sympify, Symbol

from skimpy.sampling.utils import calc_max_eigenvalue, calc_parameters
from skimpy.utils.namespace import *

from skimpy.utils.general import sanitize_cobra_vars

from skimpy.sampling.flux_concentration_sampler import FluxConcentrationSampler
from skimpy.sampling.simple_parameter_sampler import SimpleParameterSampler
from skimpy.io.generate_from_pytfa import FromPyTFA

from pytfa.analysis import  GeneralizedACHRSampler

import random, array
from deap import algorithms

from pandas import DataFrame,Series

class ItterableSeries():
    def __init__(self, this_series):
        """
        :param data: pd.Series
        """
        self.data = this_series

    def __iter__(self):
        return self.data.values.__iter__



model_gen = FromPyTFA()

class GaFluxConcentrationSampler(FluxConcentrationSampler):
    """
    This sampler performs an optimizaion 
    """

    Parameters = namedtuple('Parameters', ['n_samples',
                                           'n_parameter_samples',
                                           'max_generation',
                                           'seed',
                                           'mutation_probability',
                                           'crossover_scaling',
                                           'max_eigenvalue',
                                           'min_eigenvalue',
                                           'concentration_scaling',
                                           ])
    Parameters.__new__.__defaults__ = (None,) * len(Parameters._fields)

    def sample(
               self,
               tmodel,
               kmodel,):

        """

        :param compiled_model:
        :param flux_dict:
        :param concentration_dict:
        :param seed:
        :param max_generation:
        :param mutation_probability:
        :param eta:
        :return:
        """
        #
        from deap import base
        from deap import creator
        from deap import tools


        self.tmodel = tmodel
        self.kmodel = kmodel

        self.sampler = GeneralizedACHRSampler(tmodel, thinning=100, seed=self.parameters.seed)

        #Create the initial population from TFA Sampling
        creator.create("FitnessMax", base.Fitness, weights=(1.0, 1.0))
        creator.create("Individual", ItterableSeries, fitness=creator.FitnessMax)

        toolbox = base.Toolbox()
        toolbox.register("attr_float", self.sample_tfa_model, 1)

        toolbox.register("individual", tools.initIterate, creator.Individual, toolbox.attr_float)
        toolbox.register("population", tools.initRepeat, list, toolbox.individual)

        toolbox.register("evaluate", self.fitness)

        toolbox.register("mate", convex_mating, eta=self.parameters.crossover_scaling)
        toolbox.register("mutate", self.mutate_ind)

        toolbox.register("select", tools.selNSGA2)

        stats = tools.Statistics(lambda ind: ind.fitness.values)
        stats.register("avg", np.mean)
        stats.register("std", np.std)
        stats.register("min", np.min)
        stats.register("max", np.max)

        toolbox.pop_size = self.parameters.n_samples
        toolbox.max_gen = self.parameters.max_generation
        toolbox.mut_prob = self.parameters.mutation_probability

        flux_concentrations, log = self.run_ea(toolbox, stats=stats, verbose=True)

        # TODO: Here we will need a new data structure to return concentration sets and parameters sets
        # Best in a form so it can be cast directly to HDF5

        return flux_concentrations, log


    def fitness(self,flux_concentration):
        """
        
        """
        # Calculate the the Probility that a
        _, lamda_max, lamda_min = sample_parameters(self.kmodel,
                                                    self.tmodel,
                                                    flux_concentration,
                                                    n_samples=self.parameters.n_parameter_samples,
                                                    conc_scaling=self.parameters.concentration_scaling)

        P_lambda_max = sum([1 for i in lamda_max if i < self.parameters.max_eigenvalue ])\
                       / self.parameters.n_parameter_samples

        P_lambda_min = sum([1 for i in lamda_min if i < self.parameters.min_eigenvalue]) \
                       / self.parameters.n_parameter_samples

        return P_lambda_max, P_lambda_min


    def run_ea(self,toolbox, stats=None, verbose=False):
        pop = toolbox.population(n=toolbox.pop_size)
        #pop = toolbox.select(pop, len(pop))
        return algorithms.eaMuPlusLambda(pop, toolbox, mu=toolbox.pop_size,
                                         lambda_=toolbox.pop_size,
                                         cxpb=1-toolbox.mut_prob,
                                         mutpb=toolbox.mut_prob,
                                         stats=stats,
                                         ngen=toolbox.max_gen,
                                         verbose=verbose)


    def sample_tfa_model(self,n_samples):
        """

        :param tmodel: pytfa.tmodel
        :param n_samples: integer
        :return: TODO pd.DataFrame indexed with reaction names and metabolite concentrations
        """

        samples = self.sampler.sample(n_samples, fluxes = False)
        if samples.shape[0] == 1:
            return ItterableSeries(samples.iloc[0])

        #convert to a numpy array
        return ItterableSeries(samples)

    def mutate_ind(self,ind):
        ind.data = self.sample_tfa_model(1)
        return ind, #Very stupid but deap call is: ind, = mutate(ind)



def convex_mating(ind1,ind2, eta=0.5):
    ind1.data.data = (1-eta)*ind1.data.data + eta*ind2.data.data
    return ind1,ind2


def sample_parameters(kmodel, tmodel, individual, n_samples=1000, conc_scaling=1e6):

    """
    Run sampling on first order model
    """
    solution_raw = individual.data.data

    for name,rxn in kmodel.reactions.items():
        pytfa_reaction = tmodel.reactions.get_by_id(name)
        try:
            rxn.parameters['k_equilibrium'].value = model_gen.get_equlibrium_constant( tmodel,
                                                                              solution_raw,
                                                                              pytfa_reaction,
                                                                              scaling_factor=conc_scaling)[0]
        except KeyError:
            pass

    # Initialize parameter sampler
    sampling_parameters = SimpleParameterSampler.Parameters(n_samples=n_samples)
    sampler = SimpleParameterSampler(sampling_parameters)


    #TODO BIIIIG SHIT HERE HOW CAN WE MAKE THIS PROPERLY OR EVERY MODEL !!!!!!!!!!!!!!!!

    # Unit conversion from FBA model (Mass flux) mmol/gDW/hr to density flux mol/L/hr
    # Conversion needs gWW/gDW = 3.0 g/g and density of 1gDW 1L = 1200 gWW
    # TODO Generalize in a Unit System

    flux_dict = {reaction.id: 1e-3/(3./1200.) * conc_scaling *
                                (solution_raw[reaction.forward_variable.name] - solution_raw[reaction.reverse_variable.name])
                 for reaction in tmodel.reactions}

    # Especially this .... This is tested currently with the varma model this
    # the integer model with i.e. Nij_Biomass * 1000 is not feasible in the FBA .....
    # This this has been a crude fix so far ....
    flux_dict['LMPD_biomass_c_17_462'] = flux_dict['LMPD_biomass_c_17_462'] / 1000.0

    # M to muM
    concentration_dict = {sanitize_cobra_vars(LC.id): np.exp(solution_raw[LC.variable.name]) * conc_scaling
                          for LC in tmodel.log_concentration}

    parameter_population_lam_mu,\
        lamda_max, lamda_min = sampler.sample(kmodel,
                                             flux_dict,
                                             concentration_dict,
                                             min_max_eigenvalues=True)

    return parameter_population_lam_mu, lamda_max, lamda_min


