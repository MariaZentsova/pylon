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

"""
Controllers for network view model.

"""

#------------------------------------------------------------------------------
#  Imports:
#------------------------------------------------------------------------------

from os.path import join, dirname

from enthought.pyface.image_resource import ImageResource

from enthought.traits.ui.menu import MenuBar, ToolBar, Menu, Action

import pylon.ui.api

#------------------------------------------------------------------------------
#  Constants:
#------------------------------------------------------------------------------

ICON_LOCATION = join(dirname(pylon.ui.api.__file__), "images")

#------------------------------------------------------------------------------
#  File actions:
#------------------------------------------------------------------------------

new_action = Action(
    name="&New", accelerator="Ctrl+N", action="new_model",
    image=ImageResource("new.png", search_path=[ICON_LOCATION]),
    tooltip="New (Ctrl+N)"
)

open_action = Action(
    name="&Open", accelerator="Ctrl+O", action="open_file",
    image=ImageResource("open.png", search_path=[ICON_LOCATION]),
    tooltip="Open (Ctrl+O)"
)

save_action = Action(
    name="&Save", accelerator="Ctrl+S", action="save",
    image=ImageResource("save.png", search_path=[ICON_LOCATION]),
    tooltip="Save (Ctrl+S)"
)

import_matpower_action = Action(
    name="&MATPOWER", action="import_matpower",
    image=ImageResource("matpower.png", search_path=[ICON_LOCATION]),
    tooltip="Import MATPOWER data file"
)

import_psse_action = Action(
    name="&PSS/E", action="import_psse",
    image=ImageResource("psse.png", search_path=[ICON_LOCATION]),
    tooltip="Import PTI PSS/E data file"
)

import_psat_action = Action(
    name="P&SAT", action="psat",
    image=ImageResource("psat.png", search_path=[ICON_LOCATION]),
    tooltip="Import PSAT data file"
)

export_matpower_action = Action(
    name="&MATPOWER", action="export_matpower",
    image=ImageResource("matpower", search_path=[ICON_LOCATION]),
    tooltip="Export model to MATPOWER data file"
)

# The standard "revert all changes" action
RevertAction = Action(
    name="Revert", action="_on_revert",
    defined_when="ui.history is not None",
    enabled_when="ui.history.can_undo"
)

# The standard "close window" action
CloseAction = Action(
    name="E&xit", accelerator="Alt+X", action="_on_close",
    image=ImageResource("exit.png", search_path=[ICON_LOCATION]),
    tooltip="Exit (Alt+X)"
)

#------------------------------------------------------------------------------
#  Edit actions:
#------------------------------------------------------------------------------

# The standard "undo last change" action
UndoAction = Action(
    name="Undo", action="_on_undo", accelerator="Ctrl+Z",
    defined_when="ui.history is not None",
    enabled_when="ui.history.can_undo",
    image=ImageResource("undo.png", search_path=[ICON_LOCATION]),
    tooltip="Undo (Ctrl+Z)"
)

# The standard "redo last undo" action
RedoAction = Action(
    name="Redo", action="_on_redo", accelerator="Ctrl+Y",
    defined_when="ui.history is not None",
    enabled_when="ui.history.can_redo",
    image=ImageResource("redo.png", search_path=[ICON_LOCATION]),
    tooltip="Redo (Ctrl+Y)"
)

preferences_action = Action(
    name="&Preferences...", action="preferences",#accelerator="Ctrl+E",
    image=ImageResource("preferences.png", search_path=[ICON_LOCATION]),
    tooltip="Preferences"
)

#------------------------------------------------------------------------------
#  View actions:
#------------------------------------------------------------------------------

tree_view_action = Action(
    name="Tree", accelerator="F1", action="toggle_tree",
    image=ImageResource("tree.png", search_path=[ICON_LOCATION]),
    tooltip="Tree view (F1)"
)

table_view_action = Action(
    name="Table View", accelerator="F2", action="show_table",
    image=ImageResource("bus_table.png", search_path=[ICON_LOCATION]),
    tooltip="Table View (F2)"
)

interactive_graph_action = Action(
    name="&Interactive Graph", accelerator="F3", action="toggle_interactive",
#    image=ImageResource("graph.png", search_path=[ICON_LOCATION]),
    tooltip="Disables/Enables interactive graph (F3)",
    style="toggle"
)

bus_plot_action = Action(
    name="Bu&s Plot", accelerator="F5", action="bus_plot",
    image=ImageResource("bus_plot.png", search_path=[ICON_LOCATION]),
    tooltip="Bus Plot (F5)"
)

branch_plot_action = Action(
    name="Br&anch Plot", accelerator="F6", action="branch_plot",
    image=ImageResource("branch_plot.png", search_path=[ICON_LOCATION]),
    tooltip="Branch Plot (F6)"
)

#------------------------------------------------------------------------------
#  Network actions:
#------------------------------------------------------------------------------

bus_action = Action(
    name="B&us", accelerator="Ctrl+B", action="add_bus",
    image=ImageResource("add.png", search_path=[ICON_LOCATION]),
    tooltip="Bus (Ctrl+B)"
)

branch_action = Action(
    name="B&ranch", accelerator="Ctrl+R", action="add_branch",
    image=ImageResource("add2.png", search_path=[ICON_LOCATION]),
    tooltip="Branch (Ctrl+R)"
)

dcopf_action = Action(
    name="DC &OPF", accelerator="F12", action="dcopf",
    image=ImageResource("blank.png", search_path=[ICON_LOCATION]),
    tooltip="Run DC OPF (F12)"
)

#------------------------------------------------------------------------------
#  Help actions:
#------------------------------------------------------------------------------

# The standard "show help" action
HelpAction = Action(
    name="Help", action="show_help",
    image=ImageResource("help.png", search_path=[ICON_LOCATION]),
    tooltip="Help"
)

about_action = Action(
    name="About Pylon", action="about",
    image=ImageResource("about.png", search_path=[ICON_LOCATION]),
    tooltip="About Pylon"
)

#------------------------------------------------------------------------------
#  Menus:
#------------------------------------------------------------------------------

file_menu = Menu(
    "|", # Hack suggested by Brennan Williams to achieve correct ordering
    new_action,
    "_",
    open_action,
    save_action,
    RevertAction,
    "_",
    Menu(
        import_psat_action, import_matpower_action, import_psse_action,
        name="&Import"
    ),
    Menu(export_matpower_action, name="&Export"),
    "_",
    CloseAction,
    name="&File"
)

view_menu = Menu(
    "|",
    tree_view_action, table_view_action,
    "_",
    interactive_graph_action,
    "_",
    bus_plot_action, branch_plot_action,
    name="&View"
)

menubar = MenuBar(
    file_menu,
    Menu("|", UndoAction, RedoAction, name="&Edit"),
    view_menu,
    Menu("|", dcopf_action, "_", bus_action, branch_action, name="&Network"),
#    Menu(dot_action, name="&Graph"),
    Menu("|", HelpAction, "_", about_action, name="&Help"),
)

#------------------------------------------------------------------------------
#  Pylon "ToolBar" instance:
#------------------------------------------------------------------------------

toolbar = ToolBar(
    "|",
    CloseAction,
    "_",
    new_action, open_action, save_action,
    "_",
    UndoAction, RedoAction,
    "_",
    bus_action, branch_action, table_view_action,
    bus_plot_action, branch_plot_action,
    show_tool_names=False,
#    show_divider=False
)

# EOF -------------------------------------------------------------------------
