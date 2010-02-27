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
    ZeroOrMore, Optional, alphas, Combine, printables, Or, MatchFirst

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
        generator_data = self._get_generator_data_construct()
        branch_data = self._get_branch_data_construct()
        wind2, wind3 = self._get_transformer_data_construct()

        # Parse case
        case = header + \
               Optional(title) + \
               OneOrMore(bus_data) + separator + \
               OneOrMore(load_data) + separator + \
               OneOrMore(generator_data) + separator + \
               OneOrMore(branch_data) + separator + \
               OneOrMore(wind2) + OneOrMore(wind3)

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
        first_line = Word('01', exact=1).suppress() + comma_sep + real + \
            restOfLine.suppress()
        first_line.setParseAction(self._push_system_base)
        return first_line


    def _get_title_construct(self):
        """ Returns a construct for the subtitle of a PSS/E file.
        """
        title = Combine(Word(printables) + restOfLine).setResultsName("title")
        sub_title = Combine(Word(printables) + restOfLine).setResultsName("sub_title")

        titles = title + sub_title
        titles.setParseAction(self._push_title)

        return  titles


    def _get_bus_data_construct(self):
        """ Returns a construct for a line of bus data.
        """
        # I, 'NAME', BASKV, IDE, GL, BL, AREA, ZONE, VM, VA, OWNER
        i = integer.setResultsName("I") + comma_sep
        bus_name = quotedString.setResultsName("NAME") + comma_sep
        base_kv = real.setResultsName("BASKV") + comma_sep
        ide = Word("1234", exact=1).setResultsName("IDE") + comma_sep

        Gsh = real.setResultsName("GL") + comma_sep
        Bsh = real.setResultsName("BL") + comma_sep

        area = Optional(integer).setResultsName("AREA") + comma_sep
        zone = Optional(integer).setResultsName("ZONE") + comma_sep
        v_magnitude = real.setResultsName("VM") + comma_sep
        v_angle = real.setResultsName("VA")

        bus_data = i + bus_name + base_kv + ide + Gsh + Bsh + \
            area + zone + v_magnitude + v_angle + restOfLine.suppress()

        bus_data.setParseAction(self._push_bus_data)
        return bus_data


    def _get_load_data_construct(self):
        """ Returns a construct for a line of load data.
        """
        # I, ID, STATUS, AREA, ZONE, PL, QL, IP, IQ, YP, YQ, OWNER
        bus_id = integer.setResultsName("I") + comma_sep
        load_id = quotedString.setResultsName("ID") + comma_sep
        status = boolean.setResultsName("STATUS") + comma_sep
        area = integer.setResultsName("AREA") + comma_sep
        zone = integer.setResultsName("ZONE") + comma_sep
        p_load = real.setResultsName("PL") + comma_sep
        q_load = real.setResultsName("QL")

        load_data = bus_id + load_id + status + area + zone + p_load + \
                    q_load + restOfLine.suppress()

        load_data.setParseAction(self._push_load_data)
        return load_data


    def _get_generator_data_construct(self):
        """ Returns a construct for a line of generator data.
        """
        #I,ID,PG,QG,QT,QB,VS,IREG,MBASE,ZR,ZX,RT,XT,GTAP,STAT,RMPCT,PT,PB,O1,F1
        #    101,'1 ',   750.000,   125.648,   400.000,  -100.000,1.01000,     0,   900.000,   0.01000,   0.30000,   0.00000,   0.00000,1.00000,1,  100.0,   800.000,    50.000,   1,0.1289,   2,0.2524,   3,0.1031,   4,0.5156
        bus_id = integer.setResultsName("I") + comma_sep
        g_id = quotedString.setResultsName("ID") + comma_sep
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
        gtap = real.setResultsName("GTAP") + comma_sep
        status = boolean.setResultsName("STAT") + comma_sep
        percent = real.setResultsName("RMPCT") + comma_sep
        p_max = real.setResultsName("PT") + comma_sep
        p_min = real.setResultsName("PB")

        generator_data = bus_id + g_id + p + q + q_max + q_min + \
            v_sched + reg_bus + base_mva + r_zero + x_zero + r_tr + x_tr + \
            gtap + status + percent + p_max + p_min + restOfLine.suppress()

        generator_data.setParseAction(self._push_generator)

        return generator_data


    def _get_branch_data_construct(self):
        """ Returns a construct for a line of branch data.
        """
        # I,J,CKT,R,X,B,RATEA,RATEB,RATEC,GI,BI,GJ,BJ,ST,LEN,O1,F1,...,O4,F4
        # 151,   -152,'1 ',   0.00260,   0.04600,   3.50000, 1200.00, 1100.00, 1000.00,  0.01000, -0.25000,  0.01100, -0.15000,1, 150.00,   1,0.2000,   2,0.3000,   3,0.4000,   4,0.1000

        # FIXME: I and J may be an extended bus name enclosed in single quotes.
        from_bus_id = integer.setResultsName("I") + comma_sep
        to_bus_id = integer.setResultsName("J") + comma_sep
        id = quotedString.setResultsName("CKT") + comma_sep
        r = real.setResultsName("R") + comma_sep
        x = real.setResultsName("X") + comma_sep
        b = real.setResultsName("B") + comma_sep
        rate_a = real.setResultsName("RATEA") + comma_sep
        rate_b = real.setResultsName("RATEB") + comma_sep
        rate_c = real.setResultsName("RATEC") + comma_sep
        g_i = real.setResultsName("GI") + comma_sep
        b_i = real.setResultsName("BI") + comma_sep
        g_j = real.setResultsName("GJ") + comma_sep
        b_j = real.setResultsName("BJ") + comma_sep
        status = boolean.setResultsName("ST") + comma_sep
        length = real.setResultsName("LEN")

        branch_data = from_bus_id + to_bus_id + id + r + x + b + \
            rate_a + rate_b + rate_c + g_i + b_i + g_j + b_j + \
            status + length + restOfLine.suppress()

        branch_data.setParseAction(self._push_branch)

        return branch_data


    def _get_transformer_data_construct(self):
        """ Returns a construct for a line of transformer data.
        """
        # I,J,K,CKT,CW,CZ,CM,MAG1,MAG2,NMETR,'NAME',STAT,O1,F1,...,O4,F4
        # R1-2,X1-2,SBASE1-2
        # WINDV1,NOMV1,ANG1,RATA1,RATB1,RATC1,COD1,CONT1,RMA1,RMI1,VMA1,VMI1,NTP1,TAB1,CR1,CX1
        # WINDV2,NOMV2

        # I,J,K,CKT,CW,CZ,CM,MAG1,MAG2,NMETR,'NAME',STAT,O1,F1,...,O4,F4
        # R1-2,X1-2,SBASE1-2,R2-3,X2-3,SBASE2-3,R3-1,X3-1,SBASE3-1,VMSTAR,ANSTAR
        # WINDV1,NOMV1,ANG1,RATA1,RATB1,RATC1,COD1,CONT1,RMA1,RMI1,VMA1,VMI1,NTP1,TAB1,CR1,CX1
        # WINDV2,NOMV2,ANG2,RATA2,RATB2,RATC2,COD2,CONT2,RMA2,RMI2,VMA2,VMI2,NTP2,TAB2,CR2,CX2
        # WINDV3,NOMV3,ANG3,RATA3,RATB3,RATC3,COD3,CONT3,RMA3,RMI3,VMA3,VMI3,NTP3,TAB3,CR3,CX3

        # Unused column of data
        unused = Literal("/").suppress()

        # 101,   151,     0,'T1',1,1,1,   0.17147,  -0.10288,2,'NUCA GSU    ',1,   1,0.3200,   2,0.3900,   3,0.1400,   4,0.1500
        # 205,   215,   216,'3 ',1,1,1,   0.00034,  -0.00340,2,'3WNDSTAT3   ',3,   2,0.2540,   2,0.1746,   3,0.3333,   4,0.2381
        i = integer.setResultsName("I") + comma_sep
        j = integer.setResultsName("J") + comma_sep
        k = integer.setResultsName("K") + comma_sep
        ckt = quotedString.setResultsName("CKT") + comma_sep
        cw = integer.setResultsName("CW") + comma_sep
        cz = integer.setResultsName("CZ") + comma_sep
        cm = integer.setResultsName("CM") + comma_sep
        mag1 = real.setResultsName("MAG1") + comma_sep
        mag2 = real.setResultsName("MAG2") + comma_sep
        nmetr = integer.setResultsName("NMETR") + comma_sep
        name = quotedString.setResultsName("NAME") + comma_sep
        status = integer.setResultsName("STAT") + comma_sep
#        o1 = integer.setResultsName("o1") + comma_sep
#        f1 = real.setResultsName("f1") + comma_sep

        trx_record1 = i + j + k + ckt + cw + cz + cm + \
            mag1 + mag2 + nmetr + name + status + restOfLine.suppress()
#            o1 + f1 + OneOrMore(unused)

        # 0.00009,   0.00758, 1200.00
        # 0.00069,   0.06667,  150.00,   0.00690,   0.60000,   20.00,   0.00453,   0.50000,   15.00,1.02605, -33.2424
        r12 = real.setResultsName("R1-2") + comma_sep
        x12 = real.setResultsName("X1-2") + comma_sep
        s_base12 = real.setResultsName("SBASE1-2")

        r23 = real.setResultsName("R2-3") + comma_sep
        x23 = real.setResultsName("X2-3") + comma_sep
        s_base23 = real.setResultsName("SBASE2-3") + comma_sep
        r31 = real.setResultsName("R3-1") + comma_sep
        x31 = real.setResultsName("X3-1") + comma_sep
        s_base31 = real.setResultsName("SBASE3-1") + comma_sep
        vm_star = real.setResultsName("VMSTAR") + comma_sep
        an_star = real.setResultsName("ANSTAR")

        wind2_record2 = r12 + x12 + s_base12
        wind3_record2 = r12 + x12 + s_base12 + comma_sep + \
                        r23 + x23 + s_base23 + \
                        r31 + x31 + s_base31 + \
                        vm_star + an_star

        # 1.00000,  21.600,   0.000, 1200.00, 1100.00, 1000.00, 1,   -101, 1.05000, 0.95000, 1.05000, 0.95000,  25, 0, 0.00021, 0.00051
        wind_v1 = real.setResultsName("WINDV1") + comma_sep
        nom_v1 = real.setResultsName("NOMV1") + comma_sep
        angle1 = real.setResultsName("ANG1") + comma_sep
        rate_a1 = real.setResultsName("RATA1") + comma_sep
        rate_b1 = real.setResultsName("RATB1") + comma_sep
        rate_c1 = real.setResultsName("RATC1") + comma_sep
        cod1 = integer.setResultsName("COD1") + comma_sep
        cont1 = integer.setResultsName("CONT1") + comma_sep
        rma1 = real.setResultsName("RMA1") + comma_sep
        rmi1 = real.setResultsName("RMI1") + comma_sep
        vma1 = real.setResultsName("VMA1") + comma_sep
        vmi1 = real.setResultsName("VMI1") + comma_sep
        ntp1 = integer.setResultsName("NTP1") + comma_sep
        tab1 = integer.setResultsName("TAB1") + comma_sep
        cr1 = real.setResultsName("CR1") + comma_sep
        cx1 = real.setResultsName("CX1")

        trx_record3 = wind_v1 + nom_v1 + angle1 + rate_a1 + \
            rate_b1 + rate_c1 + cod1 + cont1 + rma1 + rmi1 + \
            vma1 + vmi1 + ntp1 + tab1 + cr1 + cx1

        # 1.00000, 500.000
        wind2_v2 = real.setResultsName("WINDV2") + comma_sep
        nom2_v2 = real.setResultsName("NOMV2")

        wind2_record4 = wind2_v2 + nom2_v2

        wind_v2 = real.setResultsName("WINDV2") + comma_sep
        nom_v2 = real.setResultsName("NOMV2") + comma_sep
        angle2 = real.setResultsName("ANG2") + comma_sep
        rate_a2 = real.setResultsName("RATA2") + comma_sep
        rate_b2 = real.setResultsName("RATB2") + comma_sep
        rate_c2 = real.setResultsName("RATC2")# + comma_sep
#        cod2 = integer.setResultsName("COD2") + comma_sep
#        cont2 = integer.setResultsName("CONT2") + comma_sep
#        rma2 = real.setResultsName("RMA2") + comma_sep
#        rmi2 = real.setResultsName("RMI2") + comma_sep
#        vma2 = real.setResultsName("VMA2") + comma_sep
#        vmi2 = real.setResultsName("VMI2") + comma_sep
#        ntp2 = integer.setResultsName("NTP2") + comma_sep
#        tab2 = integer.setResultsName("TAB2") + comma_sep
#        cr2 = real.setResultsName("CR2") + comma_sep
#        cx2 = real.setResultsName("CX2")

        wind_v3 = real.setResultsName("WINDV3") + comma_sep
        nom_v3 = real.setResultsName("NOMV3") + comma_sep
        angle3 = real.setResultsName("ANG3") + comma_sep
        rate_a3 = real.setResultsName("RATA3") + comma_sep
        rate_b3 = real.setResultsName("RATB3") + comma_sep
        rate_c3 = real.setResultsName("RATC3")# + comma_sep
#        cod3 = integer.setResultsName("COD3") + comma_sep
#        cont3 = integer.setResultsName("CONT3") + comma_sep
#        rma3 = real.setResultsName("RMA3") + comma_sep
#        rmi3 = real.setResultsName("RMI3") + comma_sep
#        vma3 = real.setResultsName("VMA3") + comma_sep
#        vmi3 = real.setResultsName("VMI3") + comma_sep
#        ntp3 = integer.setResultsName("NTP3") + comma_sep
#        tab3 = integer.setResultsName("TAB3") + comma_sep
#        cr3 = real.setResultsName("CR3") + comma_sep
#        cx3 = real.setResultsName("CX3")

        wind3_record4 = wind_v2 + nom_v2 + angle2 + rate_a2 + \
            rate_b2 + rate_c2# + cod2 + cont2 + rma2 + rmi2 + \
#            vma2 + vmi2 + ntp2 + tab2 + cr2 + cx2

        wind3_record5 = wind_v3 + nom_v3 + angle3 + rate_a3 + \
            rate_b3 + rate_c3# + cod3 + cont3 + rma3 + rmi3 + \
#            vma3 + vmi3 + ntp3 + tab3 + cr3 + cx3

        wind2 = trx_record1 + wind2_record2 + trx_record3 + wind2_record4

        wind3 = trx_record1 + wind3_record2 + trx_record3 + wind3_record4 + \
            wind3_record5

        wind2.setParseAction(self._push_two_winding_transformer)
        wind3.setParseAction(self._push_three_winding_transformer)

        return wind2, wind3


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
        # I, 'NAME', BASKV, IDE, GL, BL, AREA, ZONE, VM, VA, OWNER
        logger.debug("Parsing bus data: %s" % tokens)

        bus = Bus()
        bus._bus_id = tokens["I"]

        bus.name = tokens["NAME"].strip("'").strip()

        bus.v_base = tokens["BASKV"]

        bus.g_shunt = tokens["GL"]
        bus.b_shunt = tokens["BL"]

        bus.v_magnitude_guess = tokens["VM"]
        bus.v_magnitude = tokens["VM"]

        bus.v_angle_guess = tokens["VA"]
        bus.v_angle = tokens["VA"]

        self.case.buses.append(bus)


    def _push_load_data(self, tokens):
        """ Adds a load to a bus.
        """
        # I, ID, STATUS, AREA, ZONE, PL, QL, IP, IQ, YP, YQ, OWNER
        logger.debug("Parsing load data: %s" % tokens)

        bus = self._get_bus(tokens["I"])

        if bus is not None:
            bus.p_demand += tokens["PL"]
            bus.q_demand += tokens["QL"]


    def _push_generator(self, tokens):
        """ Adds a generator to a bus.
        """
        #I,ID,PG,QG,QT,QB,VS,IREG,MBASE,ZR,ZX,RT,XT,GTAP,STAT,RMPCT,PT,PB,O1,F1
        logger.debug("Parsing generator data: %s" % tokens)

        bus = self._get_bus(tokens["I"])

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
        # I,J,CKT,R,X,B,RATEA,RATEB,RATEC,GI,BI,GJ,BJ,ST,LEN,O1,F1,...,O4,F4
        logger.debug("Parsing branch data: %s", tokens)

        # FIXME: Support extended bus name enclosed in single quotes.
        from_bus_id = abs(tokens["I"])
        to_bus_id = abs(tokens["J"])

        from_bus = None
        to_bus = None
        for v in self.case.buses:
            if from_bus is None:
                if v._bus_id == from_bus_id:
                    from_bus = v
            if to_bus is None:
                if v._bus_id == to_bus_id:
                    to_bus = v
            if (from_bus is not None) and (to_bus is not None):
                break
        else:
            logger.error("Bus [%d %d] not found." % (from_bus_id, to_bus_id))
            return

        branch = Branch(from_bus, to_bus)

        branch.r = tokens["R"]
        branch.x = tokens["X"]
        branch.b = tokens["B"]
        branch.rate_a = tokens["RATEA"]
        branch.rate_b = tokens["RATEB"]
        branch.rate_c = tokens["RATEC"]
        branch.online = tokens["ST"]

        self.case.branches.append(branch)


    def _push_two_winding_transformer(self, tokens):
        """ Adds a branch to the case with transformer data.
        """
        logger.debug("Parsing two winding transformer data: %s" % tokens)

        from_bus_id = abs(tokens["I"])
        to_bus_id = abs(tokens["J"])

        from_bus = None
        to_bus = None
        for v in self.case.buses:
            if from_bus is None:
                if v._bus_id == from_bus_id:
                    from_bus = v
            if to_bus is None:
                if v._bus_id == to_bus_id:
                    to_bus = v
            if (from_bus is not None) and (to_bus is not None):
                break
        else:
            logger.error("Bus [%d %d] not found." % (from_bus_id, to_bus_id))
            return

        branch = Branch(from_bus, to_bus)
        branch.online = tokens["STAT"]

        self.case.branches.append(branch)


    def _push_three_winding_transformer(self, tokens):

        logger.debug("Parsing three winding transformer data: %s" % tokens)

# EOF -------------------------------------------------------------------------
