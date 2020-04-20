#!/usr/bin/env python

""" MultiQC module to parse output from KRAKEN2 """

from __future__ import print_function
from collections import OrderedDict
import os
import logging
import re

from multiqc import config
from multiqc.modules.base_module import BaseMultiqcModule

# Initialise the logger
log = logging.getLogger(__name__)

class MultiqcModule(BaseMultiqcModule):
    """ Kraken2 module """

    def __init__(self):

        # Initialise the parent object
        super(MultiqcModule, self).__init__(name='kraken2', anchor='kraken2',
        href="https://ccb.jhu.edu/software/kraken2/",
        info="Kraken 2 is the newest version of Kraken, a taxonomic classification system using exact k-mer matches to achieve high accuracy and fast classification speeds. This classifier matches each k-mer within a query sequence to the lowest common ancestor (LCA) of all genomes containing the given k-mer. The k-mer assignments inform the classification algorithm. ")

        # Find and load any kraken2 reports
        self.kraken2_data = dict()
        for f in self.find_log_files('kraken2', filehandles=True):
            self.parse_kraken2_log(f)

        # Filter to strip out ignored sample names
        self.kraken2_data = self.ignore_samples(self.kraken2_data)

        if len(self.kraken2_data) == 0:
            raise UserWarning

        log.info("Found {} reports".format(len(self.kraken2_data)))

        # Write parsed report data to a file
        self.write_data_file(self.kraken2_data, 'multiqc_kraken2')

        # Basic Stats Table
        self.kraken2_general_stats_table()


    def parse_kraken_log(self, f):
        regex = "^\s{1,2}(\d{1,2}\.\d{1,2})\t(\d+)\t(\d+)\t([UDKPCOFGS-])\t(\d+)\s+(.+)"
        for l in f['f']:
            #TODO


            

    