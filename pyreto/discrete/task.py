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

from pybrain.rl.environments import Task

#------------------------------------------------------------------------------
#  Logging:
#------------------------------------------------------------------------------

logger = logging.getLogger(__name__)

#------------------------------------------------------------------------------
#  "ProfitTask" class:
#------------------------------------------------------------------------------

class ProfitTask(Task):
    """ Defines a task with discrete observations of the clearing price.
    """

    def getReward(self):
        """ Returns the reward corresponding to the last action performed.
        """
        t = self.env.market.period

        earnings = 0.0
        for g in self.env.generators:
            # Compute costs in $ (not $/hr).
    #        fixedCost = t * g.total_cost(0.0)
    #        variableCost = (t * g.total_cost()) - fixedCost
            costs = g.total_cost(round(g.p, 4),
                                 self.env.gencost[g]["pCost"],
                                 self.env.gencost[g]["pCostModel"])

    #        offbids = self.env.market.getOffbids(g)
            offbids = [ob for ob in self.env.last_action if ob.generator == g]

            revenue = t * sum([ob.revenue for ob in offbids])

            if g.is_load:
                earnings += costs - revenue
            else:
                earnings += revenue - costs#(fixedCost + variableCost)

            logger.debug("Generator [%s] earnings: %.2f (%.2f, %.2f)" %
                         (g.name, earnings, revenue, costs))

        logger.debug("Task reward: %.2f" % earnings)

        return earnings


    def performAction(self, action):
        """ The action vector is stripped and the only element is cast to
            integer and given to the super class.
        """
        super(ProfitTask, self).performAction(int(action[0]))

# EOF -------------------------------------------------------------------------
