#------------------------------------------------------------------------------
# Copyright (C) 2010 Richard Lincoln
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
#------------------------------------------------------------------------------

""" Defines an experiment that matches up agents with tasks and handles their
    interaction.
"""

#------------------------------------------------------------------------------
#  Imports:
#------------------------------------------------------------------------------

import logging

from itertools import cycle

from scipy import array

#from pybrain.rl.experiments import Experiment, EpisodicExperiment
#from pybrain.rl.agents.optimization import OptimizationAgent

from pyreto.util import weighted_choice

#------------------------------------------------------------------------------
#  Logging:
#------------------------------------------------------------------------------

logger = logging.getLogger(__name__)

#------------------------------------------------------------------------------
#  "MarketExperiment" class:
#------------------------------------------------------------------------------

class MarketExperiment(object):
    """ Defines a multi-agent market experiment in which loads follow an
        episodic profile.
    """

    #--------------------------------------------------------------------------
    #  "object" interface:
    #--------------------------------------------------------------------------

    def __init__(self, tasks, agents, market, profile=None,branchOutages=None):
        """ Initialises the market experiment.
        """
        super(MarketExperiment, self).__init__()
        assert len(tasks) == len(agents)

        #: Tasks associate and agent with its environment.
        self.tasks = tasks

        #: Agents capable of producing actions based on previous observations.
        self.agents = agents

        #: Market to which agents submit offers/bids.
        self.market = market

        #: Load profile.  Either a 1D array used for all episodes or a 2D array
        #  where the number of rows equals the number of episodes.
#        self._profile = None
        self._pcycle = None
        self.profile = array([1.0]) if profile is None else profile

        #: List of branch outage probabilities.
        self.branchOutages = branchOutages

        self.stepid = 0

#        self.do_optimisation = {}
#        self.optimisers = {}
#
#        for task, agent in zip(self.tasks, self.agents):
#            if isinstance(agent, OptimizationAgent):
#                self.do_optimisation[agent] = True
#                self.optimisers[agent] = agent.learner
#                self.optimisers[agent].setEvaluator(task, agent.module)
#                self.optimisers[agent].maxEvaluations = \
#                    self.optimisers[agent].numEvaluations
#            else:
#                self.do_optimisation[agent] = False

        #: Save the demand at each bus.
        self.pdemand = {}
        for bus in self.market.case.buses:
            self.pdemand[bus] = bus.p_demand


    def __getstate__(self):
        """ Prevents the cycle from being pickled.
        """
        result = self.__dict__.copy()
        del result['_pcycle']
        return result


    def __setstate__(self, dict):
        """ Sets the load profile cycle when unpickling.
        """
        self.__dict__ = dict
        self._pcycle = cycle(self.profile)

    #--------------------------------------------------------------------------
    #  "MarketExperiment" interface:
    #--------------------------------------------------------------------------

#    def getProfile(self):
#        """ Returns the active power profile for the load.
#        """
#        return self._profile
#
#
#    def setProfile(self, profile):
#        """ Sets the active power profile, updating the cycle iterator.
#        """
#        self._pcycle = cycle(profile)
#        self._profile = profile
#
#    profile = property(getProfile, setProfile)


    def doOutages(self):
        """ Applies branch outtages.
        """
        assert len(self.branchOutages) == len(self.market.case.branches)

        weights = [[(False, r), (True, 1 - (r))] for r in self.branchOutages]

        for i, ln in enumerate(self.market.case.branches):
            ln.online = weighted_choice(weights[i])
            if ln.online == False:
                print "Branch outage [%s] in period %d." %(ln.name,self.stepid)


    def reset_case(self):
        """ Returns the case to its original state.
        """
        for bus in self.market.case.buses:
            bus.p_demand = self.pdemand[bus]
        for task in self.tasks:
            for g in task.env.generators:
                g.p = task.env._g0[g]["p"]
                g.p_max = task.env._g0[g]["p_max"]
                g.p_min = task.env._g0[g]["p_min"]
                g.q = task.env._g0[g]["q"]
                g.q_max = task.env._g0[g]["q_max"]
                g.q_min = task.env._g0[g]["q_min"]
                g.p_cost = task.env._g0[g]["p_cost"]
                g.pcost_model = task.env._g0[g]["pcost_model"]
                g.q_cost = task.env._g0[g]["q_cost"]
                g.qcost_model = task.env._g0[g]["qcost_model"]
                g.c_startup = task.env._g0[g]["startup"]
                g.c_shutdown = task.env._g0[g]["shutdown"]

    #--------------------------------------------------------------------------
    #  "EpisodicExperiment" interface:
    #--------------------------------------------------------------------------

    def doEpisodes(self, number=1):
        """ Do the given numer of episodes, and return the rewards of each
            step as a list.
        """
        for episode in range(number):
            print "Starting episode %d." % episode

            # Initialise the profile cycle.
            if len(self.profile.shape) == 1: # 1D array
                self._pcycle = cycle(self.profile)
            else:
                assert self.profile.shape[0] >= number
                self._pcycle = cycle(self.profile[episode, :])

            # Scale the initial load.
            c = self._pcycle.next()
            for bus in self.market.case.buses:
                bus.p_demand = self.pdemand[bus] * c

            # Initialise agents and their tasks.
            for task, agent in zip(self.tasks, self.agents):
                agent.newEpisode()
                task.reset()

            while False in [task.isFinished() for task in self.tasks]:
                if True in [task.isFinished() for task in self.tasks]:
                    raise ValueError
                self._oneInteraction()

        self.reset_case()

    #--------------------------------------------------------------------------
    #  "Experiment" interface:
    #--------------------------------------------------------------------------

    def _oneInteraction(self):
        """ Coordinates one interaction between each agent and its environment.
        """
        self.stepid += 1

        logger.info("Entering simulation period %d." % self.stepid)

        # Apply branches outages.
        if self.branchOutages is not None:
            self.doOutages()

        # Initialise the market.
        self.market.reset()

        # Get an action from each agent and perform it.
        for task, agent in zip(self.tasks, self.agents):
#            if self.do_optimisation[agent]:
#                raise Exception("When using a black-box learning algorithm, "
#                                "only full episodes can be done.")

#            if not task.isFinished():
            observation = task.getObservation()
            agent.integrateObservation(observation)

            action = agent.getAction()
            task.performAction(action)

        # Clear the market.
        self.market.run()

        # Reward each agent appropriately.
        for task, agent in zip(self.tasks, self.agents):
#            if not task.isFinished():
            reward = task.getReward()
            agent.giveReward(reward)

        # Scale loads.
        c = self._pcycle.next()
        for bus in self.market.case.buses:
            bus.p_demand = self.pdemand[bus] * c

        logger.info("") # newline


    def reset(self):
        """ Sets initial conditions for the experiment.
        """
        self.stepid = 0

        for task, agent in zip(self.tasks, self.agents):
            task.reset()

            agent.module.reset()
            agent.history.reset()

# EOF -------------------------------------------------------------------------
