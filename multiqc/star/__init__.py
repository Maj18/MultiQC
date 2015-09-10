#!/usr/bin/env python

""" MultiQC module to parse output from STAR """

from __future__ import print_function
from collections import defaultdict, OrderedDict
import json
import logging
import mmap
import os
import re

import multiqc
from multiqc import config

# Initialise the logger
log = logging.getLogger('MultiQC : {0:<14}'.format('STAR'))

class MultiqcModule(multiqc.BaseMultiqcModule):

    def __init__(self):

        # Initialise the parent object
        super(MultiqcModule, self).__init__(log)

        # Static variables
        self.name = "STAR"
        self.anchor = "star"
        self.intro = '<p><a href="https://github.com/alexdobin/STAR" target="_blank">STAR</a> \
            is an ultrafast universal RNA-seq aligner.</p>'

        # Find and load any STAR reports
        self.star_data = dict()
        for f in self.find_log_files('Log.final.out'):
            parsed_data = self.parse_star_report(f['f'])
            if parsed_data is not None:
                if f['s_name'] in self.star_data:
                    log.debug("Duplicate sample name found! Overwriting: {}".format(f['s_name']))
                self.star_data[f['s_name']] = parsed_data

        if len(self.star_data) == 0:
            log.debug("Could not find any reports in {}".format(config.analysis_dir))
            raise UserWarning

        log.info("Found {} reports".format(len(self.star_data)))

        # Write parsed report data to a file
        self.write_csv_file(self.star_data, 'multiqc_star.txt')

        self.sections = list()

        # Basic Stats Table
        # Report table is immutable, so just updating it works
        self.star_stats_table()

        # Alignment bar plot
        # Only one section, so add to the intro
        self.intro += self.star_alignment_chart()


    def parse_star_report (self, raw_data):
        """ Parse the final STAR log file. """

        regexes = {
            'total_reads':                  r"Number of input reads \|\s+(\d+)",
            'avg_input_read_length':        r"Average input read length \|\s+([\d\.]+)",
            'uniquely_mapped':              r"Uniquely mapped reads number \|\s+(\d+)",
            'uniquely_mapped_percent':      r"Uniquely mapped reads % \|\s+([\d\.]+)",
            'avg_mapped_read_length':       r"Average mapped length \|\s+([\d\.]+)",
            'num_splices':                  r"Number of splices: Total \|\s+(\d+)",
            'num_annotated_splices':        r"Number of splices: Annotated \(sjdb\) \|\s+(\d+)",
            'num_GTAG_splices':             r"Number of splices: GT/AG \|\s+(\d+)",
            'num_GCAG_splices':             r"Number of splices: GC/AG \|\s+(\d+)",
            'num_ATAC_splices':             r"Number of splices: AT/AC \|\s+(\d+)",
            'num_noncanonical_splices':     r"Number of splices: Non-canonical \|\s+(\d+)",
            'mismatch_rate':                r"Mismatch rate per base, % \|\s+([\d\.]+)",
            'deletion_rate':                r"Deletion rate per base \|\s+([\d\.]+)",
            'deletion_length':              r"Deletion average length \|\s+([\d\.]+)",
            'insertion_rate':               r"Insertion rate per base \|\s+([\d\.]+)",
            'insertion_length':             r"Insertion average length \|\s+([\d\.]+)",
            'multimapped':                  r"Number of reads mapped to multiple loci \|\s+(\d+)",
            'multimapped_percent':          r"% of reads mapped to multiple loci \|\s+([\d\.]+)",
            'multimapped_toomany':          r"Number of reads mapped to too many loci \|\s+(\d+)",
            'multimapped_toomany_percent':  r"% of reads mapped to too many loci \|\s+([\d\.]+)",
            'unmapped_mismatches_percent':  r"% of reads unmapped: too many mismatches \|\s+([\d\.]+)",
            'unmapped_tooshort_percent':    r"% of reads unmapped: too short \|\s+([\d\.]+)",
            'unmapped_other_percent':       r"% of reads unmapped: other \|\s+([\d\.]+)",
        }
        parsed_data = {}
        for k, r in regexes.items():
            r_search = re.search(r, raw_data, re.MULTILINE)
            if r_search:
                parsed_data[k] = float(r_search.group(1))
        # Figure out the numbers for unmapped as for some reason only the percentages are given
        try:
            total_mapped = parsed_data['uniquely_mapped'] + parsed_data['multimapped'] + parsed_data['multimapped_toomany']
            unmapped_count = parsed_data['total_reads'] - total_mapped
            total_unmapped_percent = parsed_data['unmapped_mismatches_percent'] + parsed_data['unmapped_tooshort_percent'] + parsed_data['unmapped_other_percent']
            parsed_data['unmapped_mismatches'] = int(round(unmapped_count * (parsed_data['unmapped_mismatches_percent'] / total_unmapped_percent), 0))
            parsed_data['unmapped_tooshort'] = int(round(unmapped_count * (parsed_data['unmapped_tooshort_percent'] / total_unmapped_percent), 0))
            parsed_data['unmapped_other'] = int(round(unmapped_count * (parsed_data['unmapped_other_percent'] / total_unmapped_percent), 0))
        except KeyError:
            pass

        if len(parsed_data) == 0: return None
        return parsed_data


    def star_stats_table(self):
        """ Take the parsed stats from the STAR report and add them to the
        basic stats table at the top of the report """

        config.general_stats['headers']['uniquely_mapped_percent'] = '<th class="chroma-col" data-chroma-scale="YlGn" data-chroma-max="100" data-chroma-min="0"><span data-toggle="tooltip" title="STAR: % Uniquely mapped reads">% Mapped</span></th>'
        config.general_stats['headers']['uniquely_mapped'] = '<th class="chroma-col" data-chroma-scale="PuRd" data-chroma-min="0"><span data-toggle="tooltip" title="STAR: Uniquely mapped reads (millions)">M Mapped</span></th>'
        for sn, data in self.star_data.items():
            config.general_stats['rows'][sn]['uniquely_mapped_percent'] = '<td class="text-right">{:.1f}%</td>'.format(data['uniquely_mapped_percent'])
            config.general_stats['rows'][sn]['uniquely_mapped'] = '<td class="text-right">{:.1f}</td>'.format(data['uniquely_mapped']/1000000)

    def star_alignment_chart (self):
        """ Make the HighCharts HTML to plot the alignment rates """
        
        # Specify the order of the different possible categories
        keys = OrderedDict()
        keys['uniquely_mapped'] =      { 'color': '#437bb1', 'name': 'Uniquely mapped' }
        keys['multimapped'] =          { 'color': '#7cb5ec', 'name': 'Mapped to multiple loci' }
        keys['multimapped_toomany'] =  { 'color': '#f7a35c', 'name': 'Mapped to too many loci' }
        keys['unmapped_mismatches'] =  { 'color': '#e63491', 'name': 'Unmapped: too many mismatches' }
        keys['unmapped_tooshort'] =    { 'color': '#b1084c', 'name': 'Unmapped: too short' }
        keys['unmapped_other'] =       { 'color': '#7f0000', 'name': 'Unmapped: other' }
        
        # Config for the plot
        config = {
            'title': 'STAR Alignment Scores',
            'ylab': '# Reads',
            'cpswitch_counts_label': 'Number of Reads'
        }
        
        return self.plot_bargraph(self.star_data, keys, config)
