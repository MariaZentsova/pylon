#------------------------------------------------------------------------------
# Copyright (C) 2009 Richard W. Lincoln
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

""" Defines the core PowerSystemResource and ConductingEquipment entities
    shared by all applications plus common collections of those entities.
    Not all applications require all the Core entities.
"""

#------------------------------------------------------------------------------
#  Imports:
#------------------------------------------------------------------------------

from enthought.traits.api import \
    HasTraits, Str, Int, Float, List, Trait, Instance, Bool, Range, \
    Property, Enum, Any, Delegate, Tuple, Array, Disallow, cached_property

from CIM13 import Root

from CIM13.Domain \
    import Seconds, AbsoluteDateTime, UnitSymbol, UnitMultiplier


CurveStyle = Enum("straightLineYValues", "rampYValue", "constantYValue",
    "formula")

#------------------------------------------------------------------------------
#  "IdentifiedObject" class:
#------------------------------------------------------------------------------

class IdentifiedObject(Root):
    """ This is a root class to provide common naming attributes for all
        classes needing naming attributes.
    """

    # The name is a free text human readable name of the object. It may be non
    # unique and may not correlate to a naming hierarchy.
    name = Str(desc="a free text human readable name of the object")

    # The description is a free human readable text describing or naming the
    # object. It may be non unique and may not correlate to a naming hierarchy.
    description = Str(desc="a free human readable text describing or naming " \
        "the object")

#------------------------------------------------------------------------------
#  "Terminal" class:
#------------------------------------------------------------------------------

class Terminal(IdentifiedObject):
    """ An electrical connection point to a piece of conducting equipment.
        Terminals are connected at physical connection points called
        "connectivity nodes".
    """

    # ConductingEquipment has 1 or 2 terminals that may be connected to other
    # ConductingEquipment terminals via ConnectivityNodes
    ConductingEquipment = Instance(HasTraits,#"CIM13.core.ConductngEquipment",
        allow_none=False)

    #--------------------------------------------------------------------------
    #  "object" interface:
    #--------------------------------------------------------------------------

    def __init__(self, conducting_equipment, **traits):
        """ Initialises a new Terminal instance.
        """
        self.ConductingEquipment = conducting_equipment
        super(Terminal, self).__init__(**traits)

#------------------------------------------------------------------------------
#  "PowerSystemResource" class:
#------------------------------------------------------------------------------

class PowerSystemResource(IdentifiedObject):
    """ A power system resource can be an item of equipment such as a Switch,
        an EquipmentContainer containing many individual items of equipment
        such as a Substation, or an organisational entity such as Company or
        SubControlArea.  This provides for the nesting of collections of
        PowerSystemResources within other PowerSystemResources. For example,
        a Switch could be a member of a Substation and a Substation could be
        a member of a division of a Company.
    """

#------------------------------------------------------------------------------
#  "Equipment" class:
#------------------------------------------------------------------------------

class Equipment(PowerSystemResource):
    """ The parts of a power system that are physical devices, electronic or
        mechanical.
    """

    # The association is used in the naming hierarchy.
    MemberOf_EquipmentContainer = Instance(HasTraits,
        desc="used in the naming hierarchy")

#------------------------------------------------------------------------------
#  "ConductingEquipment" class:
#------------------------------------------------------------------------------

class ConductingEquipment(Equipment):
    """ The parts of the power system that are designed to carry current or
        that are conductively connected therewith. ConductingEquipment is
        contained within an EquipmentContainer that may be a Substation, or
        a VoltageLeve or a Bay within a Substation.
    """

    # Describes the phases carried by a conducting equipment.
#    phases = Enum("ABCN", "ABC", "ABN", "ACN", "BCN", "AB", "AC", "BC",
#                  "AN", "BN", "CN", "A", "B", "C", "N",
#                  desc="the phases carried by a conducting equipment")

    # ConductingEquipment has 1 or 2 terminals that may be connected to other
    # ConductingEquipment terminals via ConnectivityNodes
#    Terminals = List(Instance(Terminal), maxlen=2,# minlen=1,
#        desc="1 or 2 terminals that may be connected to other "
#        "ConductingEquipment terminals via ConnectivityNodes")
#
#
#    def _Terminals_default(self):
#        """ Trait initialiser.
#        """
#        return [Terminal(conducting_equipment=self),
#                Terminal(conducting_equipment=self)]

#------------------------------------------------------------------------------
#  "RegularTimePoint" class:
#------------------------------------------------------------------------------

class RegularTimePoint(Root):
    """ TimePoints for a schedule where the time between the points is
        constant.
    """

    # The position of the RegularTimePoint in the sequence. Note that time
    # points don't have to be sequential, i.e. time points may be omitted.
    # The actual time for a RegularTimePoint is computed by multiplying the
    # RegularIntervalSchedule.timeStep with the RegularTimePoint.sequenceNumber
    # and add the BasicIntervalSchedule.startTime.
    sequenceNumber = Int(desc="position of the RegularTimePoint in the "
        "sequence")

    # The first value at the time. The meaning of the value is defined by the
    # class inhering the RegularIntervalSchedule.
    value1 = Float(desc="first value at the time")

    # The second value at the time. The meaning of the value is defined by the
    # class inhering the RegularIntervalSchedule.
    value2 = Float(desc="second value at the time")

    # A RegularTimePoint belongs to a RegularIntervalSchedule.
    IntervalSchedule = Instance("RegularIntervalSchedule")#, allow_none=False)

    #--------------------------------------------------------------------------
    #  "object" interface:
    #--------------------------------------------------------------------------

#    def __init__(self, interval_schedule, **traits):
#        """ Initialises a new RegularIntervalSchedule instance.
#        """
#        self.IntervalSchedule = interval_schedule
#        super(RegularTimePoint, self).__init__(**traits)

#------------------------------------------------------------------------------
#  "BasicIntervalSchedule" class:
#------------------------------------------------------------------------------

class BasicIntervalSchedule(IdentifiedObject):
    """ Schedule of values at points in time.
    """

    # The time for the first time point.
    startTime = AbsoluteDateTime

    # Value1 units of measure.
    value1Unit = UnitSymbol

    # Multiplier for value1.
    value1Multiplier = UnitMultiplier

    # Value2 units of measure.
    value2Unit = UnitSymbol

    # Multiplier for value2.
    value2Multiplier = UnitMultiplier

#------------------------------------------------------------------------------
#  "RegularIntervalSchedule" class:
#------------------------------------------------------------------------------

class RegularIntervalSchedule(BasicIntervalSchedule):
    """ The schedule has TimePoints where the time between them is constant.
    """

    timeStep = Seconds

    endTime = AbsoluteDateTime

    # The point data values that define a curve.
    TimePoints = List(Instance(RegularTimePoint),# minlen=1,
        desc="point data values that define a curve")

    #--------------------------------------------------------------------------
    #  "object" interface:
    #--------------------------------------------------------------------------

#    def __init__(self, time_points, **traits):
#        """ Initialises a new RegularIntervalSchedule instance.
#        """
#        self.TimePoints = time_points
#        super(RegularIntervalSchedule, self).__init__(**traits)


    def _TimePoints_default(self):
        """ Trait initialiser.
        """
        return [RegularTimePoint(IntervalSchedule=self)]

#------------------------------------------------------------------------------
#  "Curve" class:
#------------------------------------------------------------------------------

class Curve(IdentifiedObject):
    """ Relationship between an independent variable (X-axis) and one or
        two dependent variables (Y1-axis and Y2-axis). Curves can also serve
        as schedules.
    """

    # The point data values that define a curve
    CurveScheduleDatas = List(Instance("CurveScheduleData"),
        desc="point data values that define a curve")

    # The style or shape of the curve.
    curveStyle = CurveStyle

    # Multiplier for X-axis.
    xMultiplier = UnitMultiplier

    # The X-axis units of measure.
    xUnit = UnitSymbol

    # Multiplier for Y1-axis.
    y1Multiplier = UnitMultiplier

    # The Y1-axis units of measure.
    y1Unit = UnitSymbol

    # Multiplier for Y1-axis.
    y1Multiplier = UnitMultiplier

    # The Y1-axis units of measure.
    y1Unit = UnitSymbol

#------------------------------------------------------------------------------
#  "CurveData" class:
#------------------------------------------------------------------------------

class CurveData(Root):
    """ Data point values for defining a curve or schedule.
    """

    # The point data values that define a curve.
    CurveSchedule = Instance(Curve)

    # The data value of the X-axis variable,  depending on the X-axis units
    xvalue = Float(desc="data value of the X-axis variable")

    # The data value of the  first Y-axis variable, depending on the Y-axis
    # units.
    y1value = Float(desc="data value of the  first Y-axis variable")

    # The data value of the second Y-axis variable (if present), depending on
    # the Y-axis units
    y2value = Float(desc="data value of the second Y-axis variable")

# EOF -------------------------------------------------------------------------
