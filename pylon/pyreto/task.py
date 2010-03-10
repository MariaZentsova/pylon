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

""" Defines a profit maximisation task.
"""

#------------------------------------------------------------------------------
#  Imports:
#------------------------------------------------------------------------------

import logging
from scipy import array, linspace
from pybrain.rl.environments import Task

logger = logging.getLogger(__name__)

BIGNUM = 1e06

#------------------------------------------------------------------------------
#  "BaseProfitTask" class:
#------------------------------------------------------------------------------

class BaseProfitTask(Task):
    """ Defines a base task where reward is profit (revenue - cost).
    """

#    def __init__(self, environment, num_actions=10):
#        """ The action space is divided into the given number of steps.
#        """
#        super(ProfitTask, self).__init__(environment)
#
#        # The number of steps that the action value should be divided into.
##        self.action_steps = num_actions
#        self.action_space = self.getDiscreteActions(num_actions)

    #--------------------------------------------------------------------------
    #  "Task" interface:
    #--------------------------------------------------------------------------

#    def getObservation(self):
#        """ The vector of sensor values is replaced by a single integer since
#            there is only one state.
#        """
#        return 0
#
#
#    def performAction(self, action):
#        """ The action vector is stripped and the only element is cast to
#            integer and given to the super class.
#        """
##        Task.performAction(self, int(action[0]))
#        idx = int(action[0])
#        Task.performAction(self, array([self.action_space[idx]]))


    def getReward(self):
        """ Returns the reward corresponding to the last action performed.
        """
        g = self.env.asset
        t = self.env.market.period

#        offbids = self.env.market.get_offbids(g)
        offbids = self.env.last_action

        # Compute costs in $ (not $/hr).
#        g.p_cost = self.env.marginal_cost

#        fixed_cost = t * g.total_cost(0.0)
#        variable_cost = (t * g.total_cost()) - fixed_cost
        costs = g.total_cost(round(g.p, 2),
                             self.env._p_cost,
                             self.env._pcost_model)

        revenue = t * sum([ob.revenue for ob in offbids])

        if g.is_load:
            earnings = costs - revenue
        else:
            earnings = revenue - costs#(fixed_cost + variable_cost)

        logger.debug("Profit task [%s] reward: %.2f (%.2f, %.2f)" %
                     (g.name, earnings, revenue, costs))

        return earnings

#------------------------------------------------------------------------------
#  "DiscreteTask" class:
#------------------------------------------------------------------------------

class DiscreteProfitTask(BaseProfitTask):
    """ Defines a task with discrete observations of the clearing price.
    """

    #--------------------------------------------------------------------------
    #  "object" interface:
    #--------------------------------------------------------------------------

#    def __init__(self, environment, dim_state=10):
#        """ The sensor space is divided into the given number of steps.
#        """
#        super(DiscreteProfitTask, self).__init__(environment)
#
#        # State dimensions.
#        self.dim_state = dim_state

        # The number of steps that the action value should be divided into.
#        self.action_steps = num_actions
#        self.action_space = self.getDiscreteActions(num_actions)

    #--------------------------------------------------------------------------
    #  "DiscreteTask" interface:
    #--------------------------------------------------------------------------

#    def getDiscreteActions(self, num_actions):
#        """ Returns an array of action values.
#        """
#        limit = self.env.market.price_cap
#        return linspace(0.0, limit, num_actions)

    #--------------------------------------------------------------------------
    #  "Task" interface:
    #--------------------------------------------------------------------------

    def performAction(self, action):
        """ The action vector is stripped and the only element is cast to
            integer and given to the super class.
        """
        super(DiscreteProfitTask, self).performAction(int(action[0]))


#    def getObservation(self):
#        """ The agent receives a single non-negative integer indicating the
#            band of market clearing prices in which the price from the last
#            auction exists.
#        """
#        sensors = super(DiscreteProfitTask, self).getObservation()
#        # Divide the range of market prices in to discrete bands.
#        limit = self.env.market.price_cap
#        states = linspace(0.0, limit, self.dim_state)
#        mcp = abs(sensors[2]) # Discard all other sensor data.
#        for i in range(len(states) - 1):
#            if (states[i] <= round(mcp, 4) <= states[i + 1]):
#                return array([i])
#        else:
#            raise ValueError, "MCP: %f" % mcp

#------------------------------------------------------------------------------
#  "ContinuousTask" class:
#------------------------------------------------------------------------------

class ContinuousProfitTask(BaseProfitTask):
    """ Defines a task for continuous sensor and action spaces.
    """

    def __init__(self, environment):
        """ Initialises the task.
        """
        super(ContinuousProfitTask, self).__init__(environment)

        # Limits for scaling of sensors.
        self.sensor_limits = self.getSensorLimits()

        # Limits for scaling of actors.
        self.actor_limits = self.getActorLimits()

        self.mark_max = 1.0

    #--------------------------------------------------------------------------
    #  "ContinuousTask" interface:
    #--------------------------------------------------------------------------

    def getSensorLimits(self):
        """ Returns a list of 2-tuples, e.g. [(-3.14, 3.14), (-0.001, 0.001)],
            one tuple per parameter, giving min and max for that parameter.
        """
        g = self.env.asset
        mkt = self.env.market
        case = mkt.case

        limits = []
        limits.append((0.0, BIGNUM)) # f
        limits.append((0.0, self.env.p_max)) # quantity
        limits.append((0.0, BIGNUM)) # price
        limits.append((0.0, g.total_cost(self.env.p_max))) # variable
#        c_startup = 2.0 if g.c_startup == 0.0 else g.c_startup
#        limits.append((0.0, c_startup)) # startup
#        c_shutdown = 2.0 if g.c_shutdown == 0.0 else g.c_shutdown
#        limits.append((0.0, c_shutdown)) # shutdown

        limits.extend([(0.0, b.rate_a) for b in case.branches])
        limits.extend([(-BIGNUM, BIGNUM) for b in case.branches]) # mu_flow

        limits.extend([(-180.0, 180.0) for b in case.buses]) # angle
        limits.extend([(0.0, BIGNUM) for b in case.buses]) # p_lmbda
#        limits.extend([(b.v_min, b.v_max) for b in case.buses]) # mu_vmin
#        limits.extend([(b.v_min, b.v_max) for b in case.buses]) # mu_vmax

        limits.extend([(0., g.p_max) for g in case.generators]) #pg
        limits.extend([(-BIGNUM, BIGNUM) for g in case.generators]) #g_pmax
        limits.extend([(-BIGNUM, BIGNUM) for g in case.generators]) #g_pmin

        return limits


    def getActorLimits(self):
        """ Returns a list of 2-tuples, e.g. [(-3.14, 3.14), (-0.001, 0.001)],
            one tuple per parameter, giving min and max for that parameter.
        """
        n_offbids = self.env.n_offbids
        offbid_qty = self.env.offbid_qty

        actor_limits = []
        for _ in range(n_offbids):
            if offbid_qty:
                actor_limits.append((0.0, self.env._p_max))
            actor_limits.append((0.0, self.mark_max))

        return actor_limits

# EOF -------------------------------------------------------------------------
