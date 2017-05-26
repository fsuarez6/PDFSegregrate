#!/usr/bin/env python
"""
Dependencies:
  pip install ghostscript --user
  pip install PyPDF2 --user
"""
import os
import sys
import argparse
import ghostscript
import numpy as np
from PyPDF2 import PdfFileWriter, PdfFileReader


def valid_pdf_extension(name):
  if not name.endswith('.pdf'):
    msg = 'Unknown file extension: {0}'.format(name)
    raise argparse.ArgumentTypeError(msg)
  return name


def parse_args():
  parser = argparse.ArgumentParser(
    description='Segregate your PDF into color and B&W pages/sheets')
  parser.add_argument('pdf', type=valid_pdf_extension,
    help='PDF file to be process')
  parser.add_argument('--two-sided', action='store_true', 
    help='If set, will group pages for consistent two-sided printing')
  return parser.parse_args()


class PageColorInfo():
  BLANK = 'Blank'
  COLOR = 'Color'
  BW    = 'B&W'
  def __init__(self, cmyk, page_number):
    self.k = cmyk[3]
    self.cmy = np.array(cmyk[:3])
    self.page_number = page_number
  
  def __repr__(self):
    number = self.get_number()
    ptype = self.get_type()
    return '<Page: {0}: {1}>'.format(number, ptype) 
  
  def __str__(self):
    return self.__repr__()
  
  def get_black_coverage(self):
    return self.k
  
  def get_color_coverage(self):
    return np.sum(self.cmy)
  
  def get_number(self):
    return self.page_number
  
  def get_type(self):
    if self.is_color_page():
      ptype = self.COLOR
    elif self.is_blank_page():
      ptype = self.BLANK
    else:
      ptype = self.BW
    return ptype
  
  def is_color_page(self):
    return (self.get_color_coverage() > 0)
  
  def is_blank_page(self):
    inkcov = self.get_color_coverage() + self.k
    return (inkcov > 0)


if __name__ == '__main__':
  args = parse_args()
  basename = os.path.splitext(os.path.basename(args.pdf))[0]
  # Use Ghostscript to extract color information
  # TODO: Use threads to speed-up this part
  infofile = basename + '.txt'
  gsargs  = [os.path.basename(sys.argv[0])]
  gsargs += ['-q', '-dBATCH', '-dNOPAUSE', '-sDEVICE=inkcov']
  gsargs += ['-o', infofile, args.pdf]
  ghostscript.Ghostscript(*gsargs)
  # Get the pages with color
  # Shape will be rows=num_pages, cols=4 (CMYK)
  pages = []
  with open(os.path.expanduser(infofile), 'rb') as f:
    for i,line in enumerate(f):
      line = line.replace('  ', ' ')
      fields = line.split()
      if not len(fields) == 6:
        continue
      cmyk = map(float, fields[:4])
      number = i+1
      page_info = PageColorInfo(cmyk, number)
      pages.append(page_info)
  
  # Debug
  import IPython
  IPython.embed()
