"""Dataset plugins package.

Import all plugins here so discover_plugins() can find them via
DatasetPlugin.__subclasses__().
"""

from linked_past.datasets.crro.plugin import CRROPlugin
from linked_past.datasets.dprr.plugin import DPRRPlugin
from linked_past.datasets.edh.plugin import EDHPlugin
from linked_past.datasets.nomisma.plugin import NomismaPlugin
from linked_past.datasets.ocre.plugin import OCREPlugin
from linked_past.datasets.periodo.plugin import PeriodOPlugin
from linked_past.datasets.rpc.plugin import RPCPlugin
from linked_past.datasets.pleiades.plugin import PleiadesPlugin

__all__ = [
    "CRROPlugin",
    "DPRRPlugin",
    "EDHPlugin",
    "NomismaPlugin",
    "OCREPlugin",
    "PeriodOPlugin",
    "PleiadesPlugin",
    "RPCPlugin",
]
