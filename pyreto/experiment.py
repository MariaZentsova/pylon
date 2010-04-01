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

import time
import logging

from itertools import cycle

#from pybrain.rl.experiments import Experiment, EpisodicExperiment
from pybrain.rl.agents.optimization import OptimizationAgent

#------------------------------------------------------------------------------
#  Logging:
#------------------------------------------------------------------------------

logger = logging.getLogger(__name__)

#------------------------------------------------------------------------------
#  "MarketExperiment" class:
#------------------------------------------------------------------------------

class MarketExperiment(object):
    """ Defines an experiment that matches up agents with tasks and handles
        their interaction.
    """
    #--------------------------------------------------------------------------
    #  "object" interface:
    #--------------------------------------------------------------------------

    def __init__(self, tasks, agents, market):
        """ Initialises the market experiment.
        """
        super(MarketExperiment, self).__init__(None, None)

        assert len(tasks) == len(agents)

        # Tasks associate and agent with its environment.
        self.tasks = tasks

        # Agents capable of producing actions based on previous observations.
        self.agents = agents

        # Market to which agents submit offers/bids.
        self.market = market

        self.stepid = 0

    #--------------------------------------------------------------------------
    #  "Experiment" interface:
    #--------------------------------------------------------------------------

    def doInteractions(self, number=1):
        """ Directly maps the agents and the tasks.
        """
        t0 = time.time()

        for _ in range(number):
            self._oneInteraction()

        elapsed = time.time() - t0
        logger.info("%d interactions executed in %.3fs." % (number, elapsed))

        return self.stepid


    def _oneInteraction(self):
        """ Coordinates one interaction between each agent and its environment.
        """
        self.stepid += 1

        logger.info("\nEntering simulation period %d." % self.stepid)

        # Initialise the market.
        self.market.reset()

        # Get an action from each agent and perform it.
        for task, agent in zip(self.tasks, self.agents):
            observation = task.getObservation()
            agent.integrateObservation(observation)

            action = agent.getAction()
            task.performAction(action)

        # Clear the market.
        self.market.run()

        # Reward each agent appropriately.
        for task, agent in zip(self.tasks, self.agents):
            reward = task.getReward()
            agent.giveReward(reward)

        # Instruct each agent to learn from it's actions.
#        for agent in self.agents:
#            agent.learn()

#        logger.info("")


    def reset(self):
        """ Sets initial conditions for the experiment.
        """
        self.stepid = 0

        for task, agent in zip(self.tasks, self.agents):
            task.env.reset()

            agent.module.reset()
            agent.history.reset()
#            agent.history.clear()

#------------------------------------------------------------------------------
#  "EpisodicMarketExperiment" class:
#------------------------------------------------------------------------------

class EpisodicMarketExperiment(object):
    """ Defines a multi-agent market experiment in which loads follow an
        episodic profile.
    """

    #--------------------------------------------------------------------------
    #  "object" interface:
    #--------------------------------------------------------------------------

    def __init__(self, tasks, agents, market, profile=None):
        """ Initialises the market experiment.
        """
        super(EpisodicMarketExperiment, self).__init__(None, None)

        assert len(tasks) == len(agents)

        # Tasks associate and agent with its environment.
        self.tasks = tasks

        # Agents capable of producing actions based on previous observations.
        self.agents = agents

        # Market to which agents submit offers/bids.
        self.market = market

        # Load profile.
        self._profile = None
        self._p_cycle = None
        self.profile = [1.0] if profile is None else profile

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

        # Save the demand at each bus.
        self.p_orig = {}
        for bus in self.market.case.buses:
            self.p_orig[bus] = bus.p_demand


    def __getstate__(self):
        """ Prevents the cycle from being pickled.
        """
        result = self.__dict__.copy()
        del result['_p_cycle']
        return result


    def __setstate__(self, dict):
        """ Sets the load profile cycle when unpickling.
        """
        self.__dict__ = dict
        self._p_cycle = cycle(self.profile)

    #--------------------------------------------------------------------------
    #  "EpisodicMarketExperiment" interface:
    #--------------------------------------------------------------------------

    def get_profile(self):
        """ Returns the active power profile for the load.
        """
        return self._profile


    def set_profile(self, profile):
        """ Sets the active power profile, updating the cycle iterator.
        """
        self._p_cycle = cycle(profile)
        self._profile = profile

    profile = property(get_profile, set_profile)

    #--------------------------------------------------------------------------
    #  "EpisodicExperiment" interface:
    #--------------------------------------------------------------------------

    def doEpisodes(self, number=1):
        """ Do the given numer of episodes, and return the rewards of each
            step as a list.
        """
        for _ in range(number):
            # Restore original load levels.
            for bus in self.market.case.buses:
                bus.p_demand = self.p_orig[bus]

            # Initialise agents and their tasks.
            for task, agent in zip(self.tasks, self.agents):
                agent.newEpisode()
                task.reset()

            while False in [task.isFinished() for task in self.tasks]:
                if True in [task.isFinished() for task in self.tasks]:
                    raise ValueError
                self._oneInteraction()

    #--------------------------------------------------------------------------
    #  "Experiment" interface:
    #--------------------------------------------------------------------------

    def _oneInteraction(self):
        """ Coordinates one interaction between each agent and its environment.
        """
        self.stepid += 1

        logger.info("Entering simulation period %d." % self.stepid)

        # Initialise the market.
        self.market.reset()

        # Get an action from each agent and perform it.
        for task, agent in zip(self.tasks, self.agents):
#            if self.do_optimisation[agent]:
#                raise Exception("When using a black-box learning algorithm, "
#                                "only full episodes can be done.")
            if not task.isFinished():
                observation = task.getObservation()
                agent.integrateObservation(observation)

                action = agent.getAction()
                task.performAction(action)

        # Clear the market.
        self.market.run()

        # Reward each agent appropriately.
        for task, agent in zip(self.tasks, self.agents):
            if not task.isFinished():
                reward = task.getReward()
                agent.giveReward(reward)

        # Scale loads.
        c = self._p_cycle.next()
        for bus in self.market.case.buses:
            bus.p_demand = self.p_orig[bus] * c

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
