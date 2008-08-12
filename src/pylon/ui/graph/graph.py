#------------------------------------------------------------------------------
# Copyright (C) 2007 Richard W. Lincoln
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

""" Interactive graph of a pylon network """

#------------------------------------------------------------------------------
#  Imports:
#------------------------------------------------------------------------------

from os.path import join, dirname

from enthought.traits.api import HasTraits, Instance, Property, Enum
from enthought.traits.ui.api import View, Group, Item
from enthought.pyface.image_resource import ImageResource

from enthought.enable.api import \
    Window, Viewport, Scrolled, Canvas, Container, Component

from enthought.enable.tools.api import ViewportPanTool

from pylon.api import Network
from pylon.ui.graph.network_dot import NetworkDot
from pylon.ui.graph.pydot.pydot import Dot, graph_from_dot_data

from xdot_parser import XDotParser

from graph_editor import GraphEditor

#-----------------------------------------------------------------------------
#  Constants:
#-----------------------------------------------------------------------------

ICON_LOCATION = join(dirname(__file__), "../images")

frame_icon = ImageResource(join(ICON_LOCATION, "frame.ico"))

#------------------------------------------------------------------------------
#  "Graph" class:
#------------------------------------------------------------------------------

class Graph(HasTraits):
    """
    Interactive graph of a pylon network

    """

    network = Instance(
        Network,
#        allow_none=False,
        desc="the network being graphed"
    )

#    listener = Instance(
#        DotListener,
#        desc="the network listener that maintains the dot representation"
#    )

    # XDot representation of the Network
    network_dot = Instance(
        NetworkDot,
        NetworkDot(),
        allow_none=False,
        desc="dot representation of the network"
    )

    xdot = Property(
        Instance(Dot),
        depends_on=["network_dot.updated", "program"],
        desc="xdot representation with additional layout information"
    )

    program = Enum(
        "dot", "circo", "fdp", "neato", "twopi",
        desc="graph layout engine"
    )

    parser = Instance(
        XDotParser,
        XDotParser(),
        desc=" the parser of xdot code that returns or populates a container"
    )

#    container = Property(
#        Instance(Container),
#        depends_on=["xdot"],
#        desc="container of network components"
#    )

    canvas = Instance(
        Canvas,
        Canvas(bgcolor="lightsteelblue"),#, draw_axes=True),
        desc="the canvas on to which network components are drawn"
    )

    viewport = Instance(
        Viewport,
        desc="a view into a sub-region of the canvas"
    )

    config = View(
        Item(name="program"),
        Item(name="network_dot", style="custom", show_label=False),
        title="Configuration",
        icon=frame_icon,
        buttons=["OK"],
        close_result=True
    )

    traits_view=View(
        Item(
            name="viewport",
            show_label=False,
            editor=GraphEditor(),
            id='.graph_container'
        ),
        id="pylon.ui.graph.graph_view",
        resizable=True,
        width=.6,
        height=.4
    )

    def _viewport_default(self):
        """
        Trait initialiser

        """

        vp = Viewport(component=self.canvas, enable_zoom=True)
        vp.view_position = [0,0]
        vp.tools.append(ViewportPanTool(vp))
        return vp


    def _network_changed(self, new):
        """
        Handle the network changing

        """

        if self.network_dot is not None:
            self.network_dot.network = new


    def _get_xdot(self):
        """
        Property getter that is called when the network dot is
        updated or a new layout program is selected.

        """

        code = self.network_dot.dot.create(self.program, "xdot")
        return graph_from_dot_data(code)


    def _xdot_changed(self, new):
        """
        Removes all components from the canvas and gets the
        xdot parser to repopulate it.

        """

        # Empty the canvas of components
        for component in self.canvas.components:
            self.canvas.remove(component)

        self.parser.parse(new, self.canvas)

#        from enthought.enable.primitives.api import Box
#        box = Box(color="red", bounds=[50, 50], position=self.pos, resizable="")
#        self.canvas.add(box)
#        self.pos[0] += 50
#        self.pos[1] += 50

        self.viewport.request_redraw()

# EOF -------------------------------------------------------------------------
