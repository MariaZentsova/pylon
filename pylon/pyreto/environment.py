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

""" Defines an environment for market participants.
"""

#------------------------------------------------------------------------------
#  Imports:
#------------------------------------------------------------------------------

import logging
from scipy import array, zeros, r_

#from pybrain.rl.environments import Environment
from pybrain.rl.environments.graphical import GraphicalEnvironment

#from pylon import Generator
from pylon.pyreto.smart_market import Offer, Bid

logger = logging.getLogger(__name__)

#------------------------------------------------------------------------------
#  "ParticipantEnvironment" class:
#------------------------------------------------------------------------------

class ParticipantEnvironment(GraphicalEnvironment):
    """ Defines the world in which an agent acts.  It receives an input with
        .performAction() and returns an output with .getSensors(). Each
        environment requires a reference to an asset (Generator) and the whole
        power system. The parameters of the asset are changed with the
        .performAction() method.
    """

    #--------------------------------------------------------------------------
    #  "Environment" interface:
    #--------------------------------------------------------------------------

    # The number of action values the environment accepts.
#    indim = 2

    # The number of sensor values the environment produces.
#    outdim = 1

    #--------------------------------------------------------------------------
    #  "object" interface:
    #--------------------------------------------------------------------------

    def __init__(self, asset, market, markups=(0,10,20,30), n_offbids=1):
        """ Initialises the environment.
        """
        super(ParticipantEnvironment, self).__init__()

        # Generator instance that the agent controls.
        self.asset = asset

        # Auction that clears offer and bids using OPF results.
        self.market = market

        # Number of offers/bids a participant submits.
        self.n_offbids = n_offbids

        # Does a participant's offer/bid comprise quantity aswell as price.
#        self.offbid_qty = offbid_qty

        # A non-negative amount of money.
#        money = 1e6

        # Record capacity limits and the cost function on instantiation as the
        # marginal cost function since these values are changed to reflect
        # submitted offers and bids.
        self.p_max = asset.p_max
        self.p_min = asset.p_min

        # Marginal cost function proportional to current capacity.  Agents may
        # offer/bid above or below marginal cost.
        self.p_cost = asset.p_cost
        self.pcost_model = asset.pcost_model

#        # Amortised fixed costs.
#        self.c_startup = asset.c_startup
#        self.c_shutdown = asset.c_shutdown

#        if asset.is_load:
#            # Income received each periods.
#            self.endowment_profile = 10
#            # Needs and preferences for power consumption each period.
#            self.utility_function = [1.0]
#            # Savings from previous periods.
#            self.savings = 100
#            # Each participant is a shareholder who owns shares in generating
#            # companies and receives an according dividend each period.
#            self.shares = {}

#        self.render = render
#        if self.render:
#            self.updateDone = True
#            self.updateLock=threading.Lock()

        self.all_actions = list(xselections(markups, n_offbids))

        #----------------------------------------------------------------------
        # Set the number of action values that the environment accepts.
        #----------------------------------------------------------------------

#        if offbid_qty:
#            self.indim = n_offbids * 2
#        else:
#            self.indim = n_offbids

        # One (cumulative) markup per segment.
        self.indim = len(asset.p_cost) * 4

        #----------------------------------------------------------------------
        # Set the number of sensor values that the environment produces.
        #----------------------------------------------------------------------

        outdim = 0
        outdim += 3 # Dispatch sensors.
        outdim += len(market.case.branches) * 2 # Branch sensors.
        outdim += len(market.case.buses) * 2 # Bus sensors.
        outdim += len(market.case.generators) * 3 # Generator sensors.
        self.outdim = outdim

    #--------------------------------------------------------------------------
    #  "Environment" interface:
    #--------------------------------------------------------------------------

    def getSensors(self):
        """ Returns the currently visible state of the world as a numpy array
            of doubles.
        """
        g = self.asset
        case = self.market.case

        if not g.is_load:
            offbids = [x for x in self.market.offers if x.generator == g]
        else:
            offbids = [x for x in self.market.bids if x.vload == g]

        # Dispatch related sensors.
        dispatch_sensors = zeros(3)

        if self.market._solution.has_key("f"):
            dispatch_sensors[0] = self.market._solution["f"]
        dispatch_sensors[1] = sum([ob.cleared_quantity for ob in offbids])
        if offbids:
            dispatch_sensors[2] = offbids[0].cleared_price
#        dispatch_sensors[3] = dispatch.variable
#        dispatch_sensors[4] = dispatch.startup
#        dispatch_sensors[5] = dispatch.shutdown

        # Case related sensors.
        flows = array([branch.p_from for branch in case.branches])
        mu_flow = array([branch.mu_s_from for branch in case.branches])
        voltages = array([bus.v_magnitude for bus in case.buses])
        angles = array([bus.v_angle for bus in case.buses])
        nodal_prc = array([bus.p_lmbda for bus in case.buses])
        v_max = array([bus.mu_vmax for bus in case.buses])
        v_min = array([bus.mu_vmin for bus in case.buses])
        pg = array([g.p for g in case.generators])
        g_max = array([g.mu_pmax for g in case.generators])
        g_min = array([g.mu_pmin for g in case.generators])

        case_sensors = r_[flows, mu_flow, angles, nodal_prc, pg, g_max, g_min]

#        if self.hasRenderer():
#            renderer = self.getRenderer()

        return r_[dispatch_sensors, case_sensors]


    def performAction(self, action):
        """ Performs an action on the world that changes it's internal state.
            @param action: an action that should be executed in the Environment
            @type action: array: [ qty, prc, qty, prc, ... ]
        """
        asset = self.asset
        mkt = self.market
        n_offbids = self.n_offbids
        p_cost = self.p_cost

        a = self.all_actions[ int(action[0]) ]

        # Divide the rated capacity equally among the offers/bids.
        qty = self.p_max / n_offbids
        for i in range(n_offbids):
            n_segments = len(p_cost) - 1
            # Markup each piece-wise linear segments.
            for j in range(n_segments):
                x1, y1 = p_cost[j]
                x2, y2 = p_cost[j + 1]
                if x1 <= qty <= x2:
                    m = (y2 - y1) / (x2 - x1)
                    # cumulative markup to ensure convexity
                    prc = m * sum(a[:i])
                    break

            if not asset.is_load:
                mkt.offers.append(Offer(asset, qty, prc))
                logger.info("%.2fMW offered at %.2f$/MWh for %s." %
                            (qty, prc, asset.name))
            else:
                mkt.bids.append(Bid(asset, qty, prc))
                logger.info("%.2f$/MWh bid for %.2fMW to supply %s." %
                            (prc, qty, asset.name))


        # Participants either submit prices, where the quantity is divided
        # equally among the offers/bids, or tuples of quantity and price.
#        if not self.offbid_qty:
#            # Divide the rated capacity equally among the offers/bids.
#            qty = self.p_max / n_offbids
#            for prc in action:
#                if not asset.is_load:
#                    mkt.offers.append(Offer(asset, qty, prc))
#                    logger.info("%.2fMW offered at %.2f$/MWh for %s." %
#                                (qty, prc, asset.name))
#                else:
#                    mkt.bids.append(Bid(asset, qty, prc))
#                    logger.info("%.2f$/MWh bid for %.2fMW to supply %s." %
#                                (prc, qty, asset.name))
#        else:
#            # Agent's actions comprise both quantities and prices.
#            for i in range(0, len(action), 2):
#                qty = action[i]
#                prc = action[i + 1]
#                if not asset.is_load:
#                    mkt.offers.append(Offer(asset, qty, prc))
#                    logger.info("%.2fMW offered at %.2f$/MWh for %s." %
#                                (qty, prc, asset.name))
#                else:
#                    mkt.bids.append(Bid(asset, qty, prc))
#                    logger.info("%.2f$/MWh bid for %.2fMW to supply %s." %
#                                (prc, qty, asset.name))

#        if self.hasRenderer():
#            render = self.getRenderer()


    def reset(self):
        """ Reinitialises the environment.
        """
        self.market.init()


def xselections(items, n):
    if n==0: yield []
    else:
        for i in xrange(len(items)):
            for ss in xselections(items, n-1):
                yield [items[i]]+ss

# EOF -------------------------------------------------------------------------
