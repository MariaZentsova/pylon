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

""" For writing case data to file as Comma Separated Values (CSV).
"""

#------------------------------------------------------------------------------
#  Imports:
#------------------------------------------------------------------------------

import csv

from common import CaseWriter, BUS_ATTRS, BRANCH_ATTRS, GENERATOR_ATTRS

#------------------------------------------------------------------------------
#  "CSVWriter" class:
#------------------------------------------------------------------------------

class CSVWriter(CaseWriter):
    """ Writes case data to file as CSV.
    """

    #--------------------------------------------------------------------------
    #  "object" interface:
    #--------------------------------------------------------------------------

    def __init__(self, case):
        """ Initialises a new CSVWriter instance.
        """
        super(CSVWriter, self).__init__(case)

        # For writing CSV files.
        self.writer = None

    #--------------------------------------------------------------------------
    #  "CaseReader" interface:
    #--------------------------------------------------------------------------

    def write(self, file_or_filename):
        """ Writes case data as CSV.
        """
        if isinstance(file_or_filename, basestring):
            file = open(file_or_filename, "wb")
        else:
            file = file_or_filename

        self.writer = csv.writer(file)

        super(CSVWriter, self).write(file)


    def write_case_data(self, file):
        """ Writes the case data as CSV.
        """
        writer = self._get_writer(file)
        writer.writerow(["Name", "base_mva"])
        writer.writerow([self.case.name, self.case.base_mva])


    def write_bus_data(self, file):
        """ Writes bus data as CSV.
        """
        writer = self._get_writer(file)
        writer.writerow(BUS_ATTRS)
        for bus in self.case.buses:
            writer.writerow([getattr(bus, attr) for attr in BUS_ATTRS])


    def write_branch_data(self, file):
        """ Writes branch data as CSV.
        """
        writer = self._get_writer(file)
        writer.writerow(BRANCH_ATTRS)
        for branch in self.case.branches:
            writer.writerow([getattr(branch, a) for a in BRANCH_ATTRS])


    def write_generator_data(self, file):
        """ Write generator data as CSV.
        """
        writer = self._get_writer(file)
        writer.writerow(["bus"] + GENERATOR_ATTRS)

        for g in self.case.generators:
            i = self.case.buses.index(g.bus)
            writer.writerow([i] + [getattr(g,a) for a in GENERATOR_ATTRS])

    #--------------------------------------------------------------------------
    #  "CSVReader" interface:
    #--------------------------------------------------------------------------

    def _get_writer(self, file):
        if self.writer is None:
            return csv.writer(file)
        else:
            return self.writer

# EOF -------------------------------------------------------------------------
