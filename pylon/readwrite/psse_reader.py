#------------------------------------------------------------------------------
# Copyright (C) 2010 Richard Lincoln
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 dated June, 1991.
#
# This software is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANDABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301 USA
#------------------------------------------------------------------------------

""" Defines a reader for PSS/E data files.
"""

#------------------------------------------------------------------------------
#  Imports:
#------------------------------------------------------------------------------

import time
import logging

from parsing_util \
    import integer, boolean, real, psse_comment, comma_sep

from pyparsing \
    import Literal, Word, restOfLine, printables, quotedString, OneOrMore, \
    ZeroOrMore, Optional, alphas, Combine, printables

from pylon import Case, Bus, Branch, Generator

from pylon.readwrite.common import CaseReader

#------------------------------------------------------------------------------
#  Logging:
#------------------------------------------------------------------------------

logger = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
#  "PSSEReader" class:
#-------------------------------------------------------------------------------

class PSSEReader(CaseReader):
    """ Defines a reader of PSS/E data files that returns a case object.
    """

    #--------------------------------------------------------------------------
    #  "CaseReader" interface:
    #--------------------------------------------------------------------------

    def read(self, file_or_filename):
        """ Parses a PSS/E data file and returns a case object.
        """
        self.file_or_filename = file_or_filename

        logger.info("Parsing PSS/E case file [%s]." % file_or_filename)
        t0 = time.time()

        self.case = Case()

        header = self._get_header_construct()
        title = self._get_title_construct()
        bus_data = self._get_bus_data_construct()
        separator = self._get_separator_construct()
        load_data = self._get_load_data_construct()
        fixed_shunt_data = self._get_fixed_shunt_construct()
        generator_data = self._get_generator_data_construct()
        branch_data = self._get_branch_data_construct()
        transformer_data = self._get_transformer_data_construct()

        # Parse case
        case = ZeroOrMore(psse_comment) + header + \
               ZeroOrMore(psse_comment) + Optional(title) + \
               ZeroOrMore(psse_comment) + OneOrMore(bus_data) + \
               ZeroOrMore(psse_comment) + separator + \
               ZeroOrMore(psse_comment) + ZeroOrMore(load_data) + \
               ZeroOrMore(psse_comment) + separator + \
               ZeroOrMore(psse_comment) + ZeroOrMore(fixed_shunt_data) + \
               ZeroOrMore(psse_comment) + separator + \
               ZeroOrMore(psse_comment) + OneOrMore(generator_data)# + \
#               ZeroOrMore(psse_comment) + separator + \
#               ZeroOrMore(psse_comment) + ZeroOrMore(branch_data) + \
#               ZeroOrMore(psse_comment) + separator + \
#               ZeroOrMore(psse_comment) + ZeroOrMore(transformer_data) + \
#               ZeroOrMore(psse_comment)

        case.parseFile(file_or_filename)

        elapsed = time.time() - t0
        logger.info("PSS/E case file parsed in %.3fs." % elapsed)

        return self.case

    #--------------------------------------------------------------------------
    #  "PSSEReader" interface:
    #--------------------------------------------------------------------------

    def _get_separator_construct(self):
        """ Returns a construct for a PSS/E separator.
        """
        # Tables are separated by a single 0
        comment = Optional(restOfLine).setResultsName("comment")
        separator = Literal('0') + comment
        separator.setParseAction(self._push_separator)

        return separator


    def _get_header_construct(self):
        """ Returns a construct for the header of a PSS/E file.
        """
        first_line = Word('0', exact=1).suppress() + comma_sep + real + \
            restOfLine.suppress()
        first_line.setParseAction(self._push_system_base)
        return first_line


    def _get_title_construct(self):
        """ Returns a construct for the subtitle of a PSS/E file.
        """
#        title = Word(alphas).suppress() + restOfLine.suppress()
#        sub_title = Word(printables) + restOfLine.suppress()
        title = Combine(Word(printables) + restOfLine).setResultsName("title")
        sub_title = Combine(Word(printables) + restOfLine).setResultsName("sub_title")

        titles = title + sub_title
        titles.setParseAction(self._push_title)

        return  titles


    def _get_bus_data_construct(self):
        """ Returns a construct for a line of bus data.
        """
        # I, 'NAME', BASKV, IDE, GL, BL, AREA, ZONE, VM, VA, OWNER
        i = integer.setResultsName("Bus") + comma_sep
        bus_name = quotedString.setResultsName("Name") + comma_sep
        base_kv = real.setResultsName("BASKV") + comma_sep
        ide = Word("1234", exact=1).setResultsName("Type") + comma_sep

        Gsh = real.setResultsName("Gl") + comma_sep
        Bsh = real.setResultsName("Bl") + comma_sep

        area = Optional(integer).setResultsName("Area") + comma_sep
        zone = Optional(integer).setResultsName("Zone") + comma_sep
        v_magnitude = real.setResultsName("PU_Volt") + comma_sep
        v_angle = real.setResultsName("Angle")

        bus_data = i + bus_name + base_kv + ide + Gsh + Bsh + \
            area + v_magnitude + v_angle + restOfLine.suppress()

        bus_data.setParseAction(self._push_bus_data)
        return bus_data


    def _get_load_data_construct(self):
        """ Returns a construct for a line of load data.
        """
        # I, ID, STATUS, AREA, ZONE, PL, QL, IP, IQ, YP, YQ, OWNER
        bus_id = integer.setResultsName("Bus") + comma_sep
        load_id = quotedString.setResultsName("LoadID") + comma_sep
        status = boolean.setResultsName("Status") + comma_sep
        area = integer.setResultsName("Area") + comma_sep
        zone = integer.setResultsName("Zone") + comma_sep
        p_load = real.setResultsName("LP") + comma_sep
        q_load = real.setResultsName("LQ")

        load_data = bus_id + load_id + status + area + zone + p_load + \
                    q_load + restOfLine.suppress()

        load_data.setParseAction(self._push_load_data)
        return load_data


    def _get_fixed_shunt_construct(self):
        """ Returns a construct for a line of fixed shunt data.
        """
        bus_id = integer.setResultsName("Bus") + comma_sep
        shunt_id = quotedString.setResultsName("ShuntID") + comma_sep
        status = boolean.setResultsName("Status") + comma_sep
        Bsh = real.setResultsName("Bsh") + comma_sep
        Gsh = real.setResultsName("Gsh")

        shunt_data = bus_id + shunt_id + status + Bsh + Gsh + \
            restOfLine.suppress()

        shunt_data.setParseAction(self._push_fixed_shunt_data)

        return shunt_data


    def _get_generator_data_construct(self):
        """ Returns a construct for a line of generator data.
        """
        # I, ID, 'NAME', PG, QG, QT, QB, VS, IREG, MBASE, ZR, ZX, RT, XT, GTAP,
        # STAT, RMPCT, PT, PB, O1, F1, ....O4, F4
        bus_id = integer.setResultsName("Bus") + comma_sep
        g_id = integer.setResultsName("ID") + comma_sep
        g_name = quotedString.setResultsName("NAME") + comma_sep
        p = real.setResultsName("PG") + comma_sep
        q = real.setResultsName("QG") + comma_sep
        q_max = real.setResultsName("QT") + comma_sep
        q_min = real.setResultsName("QB") + comma_sep
        v_sched = real.setResultsName("VS") + comma_sep
        reg_bus = integer.setResultsName("IREG") + comma_sep
        base_mva = real.setResultsName("MBASE") + comma_sep
        r_zero = real.setResultsName("ZR") + comma_sep
        x_zero = real.setResultsName("ZX") + comma_sep
        r_tr = real.setResultsName("RT") + comma_sep
        x_tr = real.setResultsName("XT") + comma_sep
        gtap = integer.setResultsName("GTAP") + comma_sep
        status = boolean.setResultsName("STAT") + comma_sep
        percent = integer.setResultsName("RMPCT") + comma_sep
        p_max = real.setResultsName("PT") + comma_sep
        p_min = real.setResultsName("PB")

        generator_data = bus_id + g_id + g_name + p + q + q_max + q_min + \
            v_sched + reg_bus + base_mva + r_zero + x_zero + r_tr + x_tr + \
            gtap + status + percent + p_max + p_min + restOfLine.suppress()

        generator_data.setParseAction(self._push_generator)

        return generator_data


    def _get_branch_data_construct(self):
        """ Returns a construct for a line of branch data.
        """
        # From, To, ID, R, X, B, RateA, RateB, RateC, G_busI, B_busI,
        # G_busJ, B_busJ, Stat, Len
        from_bus_id = integer.setResultsName("From") + comma_sep
        to_bus_id = integer.setResultsName("To") + comma_sep
        id = integer.setResultsName("ID") + comma_sep
        r = real.setResultsName("R") + comma_sep
        x = real.setResultsName("X") + comma_sep
        b = real.setResultsName("B") + comma_sep
        rate_a = real.setResultsName("RateA") + comma_sep
        rate_b = real.setResultsName("RateB") + comma_sep
        rate_c = real.setResultsName("RateC") + comma_sep
        g_bus_i = real.setResultsName("G_busI") + comma_sep
        b_bus_i = real.setResultsName("B_busI") + comma_sep
        g_bus_j = real.setResultsName("G_busJ") + comma_sep
        b_bus_j = real.setResultsName("B_busJ") + comma_sep
        status = boolean.setResultsName("Stat") + comma_sep
        length = real.setResultsName("Len")

        branch_data = from_bus_id + to_bus_id + id + r + x + b + \
            rate_a + rate_b + rate_c + g_bus_i + b_bus_i + g_bus_j + \
            b_bus_j + status + length + restOfLine.suppress()

        branch_data.setParseAction(self._push_branch)
        return branch_data


    def _get_transformer_data_construct(self):
        """ Returns a construct for a line of transformer data.
        """
        # From, To, K, ID, CW, CZ, CM, MAG1, MAG2, NMETR, NAME, STAT, O1, F1
        # R1-2, X1-2, SBASE1-2
        # WINDV1, NOMV1, ANG1, RATA1, RATB1, RATC1, COD, CONT, RMA, RMI, VMA, VMI, NTP, TAB, CR, CX
        # WINDV2, NOMV2

        # Unused column of data
        unused = Literal("/").suppress()

        from_bus_id = integer.setResultsName("From") + comma_sep
        to_bus_id = integer.setResultsName("To") + comma_sep
        k = integer.setResultsName("K") + comma_sep
        id = integer.setResultsName("ID") + comma_sep
        cw = integer.setResultsName("CW") + comma_sep
        cz = integer.setResultsName("CZ") + comma_sep
        cm = integer.setResultsName("CM") + comma_sep
        mag1 = real.setResultsName("MAG1") + comma_sep
        mag2 = real.setResultsName("MAG2") + comma_sep
        nmetr = integer.setResultsName("NMETR") + comma_sep
        name = quotedString.setResultsName("NAME") + comma_sep
        status = boolean.setResultsName("STAT") + comma_sep
        o1 = integer.setResultsName("o1") + comma_sep
        f1 = integer.setResultsName("f1") + comma_sep

        transformer_general = from_bus_id + to_bus_id + k + id + \
            cw + cz + cm + mag1 + mag2 + nmetr + name + status + \
            o1 + f1 + OneOrMore(unused)

        r12 = real.setResultsName("R1-2") + comma_sep
        x12 = real.setResultsName("X1-2") + comma_sep
        s_base12 = real.setResultsName("SBASE1-2") + comma_sep

        transformer_impedance = r12 + x12 + s_base12 + OneOrMore(unused)

        v1_wind = real.setResultsName("WINDV1") + comma_sep
        v1_nom = real.setResultsName("NOMV1") + comma_sep
        angle1 = real.setResultsName("ANG1") + comma_sep
        rate_a1 = real.setResultsName("RATA1") + comma_sep
        rate_b1 = real.setResultsName("RATB1") + comma_sep
        rate_c1 = real.setResultsName("RATC1") + comma_sep
        cod = integer.setResultsName("COD") + comma_sep
        cont = real.setResultsName("CONT") + comma_sep
        rma = real.setResultsName("RMA") + comma_sep
        rmi = real.setResultsName("RMI") + comma_sep
        vma = real.setResultsName("VMA") + comma_sep
        vmi = real.setResultsName("VMI") + comma_sep
        ntp = real.setResultsName("NTP") + comma_sep
        tab = real.setResultsName("TAB") + comma_sep
        cr = real.setResultsName("CR") + comma_sep
        cx = real.setResultsName("CX") + comma_sep

        transformer_winding_1 = v1_wind + v1_nom + angle1 + rate_a1 + \
            rate_b1 + rate_c1 + cod + cont + rma + rmi + vma + vmi + \
            ntp + tab + cr + cx

        v2_wind = real.setResultsName("WINDV2") + comma_sep
        v2_nom = real.setResultsName("NOMV2") + comma_sep

        transformer_winding_2 = v2_wind + v2_nom + OneOrMore(unused)

        transformer_data = transformer_general + transformer_impedance + \
            transformer_winding_1 + transformer_winding_2

        transformer_data.setParseAction(self._push_transformer_data)

        return transformer_data


    def _get_bus(self, bus_id):
        """ Returns the bus with the given id or None.
        """
        for bus in self.case.buses:
            if bus._bus_id == bus_id:
                break
        else:
            logger.error("Bus [%d] not found." % bus_id)
            return None

        return bus

    #--------------------------------------------------------------------------
    #  Parse actions:
    #--------------------------------------------------------------------------

    def _push_system_base(self, tokens):
        """ Set the system base.
        """
        logger.debug("MVA Base: %.3f" % tokens[0])
        self.case.base_mva = tokens[0]


    def _push_title(self, tokens):
        """ Handles the case title.
        """
        logger.debug("Title: %s" % tokens["title"])
        logger.debug("Sub-Title: %s" % tokens["sub_title"])
        self.case.name = tokens["title"] + tokens["sub_title"]


    def _push_separator(self, tokens):
        """ Handles separators.
        """
        logger.debug("Parsed separator [%s]." % tokens["comment"])


    def _push_bus_data(self, tokens):
        """ Adds a bus to the case.
        """
        # [I, IDE, PL, QL, GL, BL, IA, VM, VA, 'NAME', BASKL, ZONE]
        # Bus, Name, Base_kV, Type, Y_re, Y_im, Area, Zone, PU_Volt, Angle
        logger.debug("Parsing bus data: %s" % tokens)

        bus = Bus()
        bus.name = tokens["Name"].strip("'").strip()
        bus._bus_id = tokens["Bus"]

        bus.v_base = tokens["BASKV"]

        bus.g_shunt = tokens["Gl"]
        bus.b_shunt = tokens["Bl"]

        bus.v_magnitude_guess = tokens["PU_Volt"]
        bus.v_magnitude = tokens["PU_Volt"]

        bus.v_angle_guess = tokens["Angle"]
        bus.v_angle = tokens["Angle"]

        self.case.buses.append(bus)


    def _push_load_data(self, tokens):
        """ Adds a load to a bus.
        """
        # I, ID, STATUS, AREA, ZONE, PL, QL, IP, IQ, YP, YQ, OWNER
        logger.debug("Parsing load data: %s" % tokens)

        bus = self._get_bus(tokens["Bus"])

        if bus is not None:
            bus.p_demand += tokens["LP"]
            bus.q_demand += tokens["LQ"]


    def _push_fixed_shunt_data(self, tokens):
        logger.debug("Parsing fixed shunt data: %s" % tokens)


    def _push_generator(self, tokens):
        """ Adds a generator to a bus.
        """
        # I, ID, PG, QG, QT, QB, VS, IREG, MBASE, ZR, ZX, RT, XT, GTAP, STAT,
        # RMPCT, PT, PB, O1, F1, ....O4, F4
        logger.debug("Parsing generator data: %s" % tokens)

        bus = self._get_bus(tokens["Bus"])

        if bus is not None:
            g = Generator(bus)
            g.p = tokens["PG"]
            g.q = tokens["QG"]
            g.q_max = tokens["QT"]
            g.q_min = tokens["QB"]
            g.v_magnitude = tokens["VS"]
            g.base_mva = tokens["MBASE"]
            g.online = tokens["STAT"]
            g.p_max = tokens["PT"]
            g.p_min = tokens["PB"]

            self.case.generators.append(g)


    def _push_branch(self, tokens):
        """ Adds a branch to the case.
        """
        # From, To, ID, R, X, B, RateA, RateB, RateC, G_busI, B_busI,
        # G_busJ, B_busJ, Stat, Len
        logger.debug("Parsing branch data: %s", tokens)

        from_bus = None
        to_bus = None
        for v in self.case.buses:
            if from_bus is None:
                if v._bus_id == tokens["From"]:
                    from_bus = v
            if to_bus is None:
                if v._bus_id == tokens["To"]:
                    to_bus = v
            if (from_bus is not None) and (to_bus is not None):
                break
        else:
            logger.error("A bus for branch from %d to %d not found" %
                         (tokens["From"], tokens["To"]))
            return

        branch = Branch(from_bus=from_bus, to_bus=to_bus)

        branch.r = tokens["R"]
        branch.x = tokens["X"]
        branch.b = tokens["B"]
        branch.rate_a = tokens["RateA"]
        branch.rate_b = tokens["RateB"]
        branch.rate_c = tokens["RateC"]
        branch.online = tokens["Stat"]

        self.case.branches.append(branch)


    def _push_transformer_data(self, tokens):
        """ Adds a branch to the case with transformer data.
        """
        logger.debug("Parsing transformer data: %s" % tokens)

        from_bus = None
        to_bus = None
        for v in self.case.buses:
            if from_bus is None:
                if v._bus_id == tokens["From"]:
                    from_bus = v
            if to_bus is None:
                if v._bus_id == tokens["To"]:
                    to_bus = v
            if (from_bus is not None) and (to_bus is not None):
                break
        else:
            logger.error("A bus for branch from %d to %d not found" %
                         (tokens["From"], tokens["To"]))
            return

        branch = Branch(from_bus=from_bus, to_bus=to_bus)
        branch.online = tokens["STAT"]

        self.case.branches.append(branch)

# EOF -------------------------------------------------------------------------
