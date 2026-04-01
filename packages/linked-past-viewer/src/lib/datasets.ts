/**
 * Static dataset metadata for popover display.
 * Sourced from datasets.yaml — does not change at runtime.
 */

export type DatasetInfo = {
  name: string;
  description: string;
  license: string;
  url: string;
};

export const DATASETS: Record<string, DatasetInfo> = {
  dprr: {
    name: "Digital Prosopography of the Roman Republic",
    description: "Persons, offices, relationships (509–31 BC)",
    license: "CC BY-NC 4.0",
    url: "https://romanrepublic.ac.uk",
  },
  pleiades: {
    name: "Pleiades: A Gazetteer of Past Places",
    description: "Ancient places — coordinates, names, time periods",
    license: "CC BY 3.0",
    url: "https://pleiades.stoa.org",
  },
  periodo: {
    name: "PeriodO",
    description: "Gazetteer of period definitions from scholarly sources",
    license: "CC0 1.0",
    url: "https://perio.do",
  },
  nomisma: {
    name: "Nomisma.org",
    description: "Numismatic concept vocabulary — persons, mints, denominations",
    license: "CC BY 4.0",
    url: "http://nomisma.org",
  },
  crro: {
    name: "Coinage of the Roman Republic Online",
    description: "Roman Republican coin types (Crawford's RRC)",
    license: "ODbL 1.0",
    url: "https://numismatics.org/crro",
  },
  ocre: {
    name: "Online Coins of the Roman Empire",
    description: "Roman Imperial coin types (RIC)",
    license: "ODbL 1.0",
    url: "https://numismatics.org/ocre",
  },
  edh: {
    name: "Epigraphic Database Heidelberg",
    description: "81,000+ Latin inscriptions with transcriptions and findspots",
    license: "CC BY-SA 4.0",
    url: "https://edh.ub.uni-heidelberg.de",
  },
};
