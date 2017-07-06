#!/usr/bin/env python
"""
Dependencies:
  pip install ghostscript --user
  pip install PyPDF2 --user
"""
import os
import sys
import time
import argparse
import ghostscript
import numpy as np
import multiprocessing
from PyPDF2 import PdfFileWriter, PdfFileReader


class PageColorInfo():
  BLANK = 'Blank'
  COLOR = 'Color'
  BW    = 'B&W'
  def __init__(self, cmyk, page_number):
    self.k = cmyk[3]
    self.cmy = np.array(cmyk[:3])
    self.page_number = page_number
    self.colorcov = np.sum(self.cmy)
    self.inkcov = self.get_color_coverage() + self.k
  
  def __repr__(self):
    number = self.get_number()
    ptype = self.get_type()
    return '<Page {0}: {1}>'.format(number, ptype) 
  
  def __str__(self):
    return self.__repr__()
  
  def get_black_coverage(self):
    return self.k
  
  def get_color_coverage(self):
    return self.colorcov
  
  def get_ink_coverage(self):
    return self.inkcov
  
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
    return (self.colorcov > 0)
  
  def is_black_page(self):
    return (self.colorcov == 0 and self.k > 0)
  
  def is_white_page(self):
    return (self.inkcov == 0)

def extract_pdf_pages(pdf, pages):
  extract = PdfFileWriter()
  for i in range(pdf.numPages):
    if (i+1) in pages:
      extract.addPage(pdf.getPage(i))
  return extract

def parse_args():
  parser = argparse.ArgumentParser(
    description='Segregate your PDF into color and B&W pages/sheets')
  parser.add_argument('pdf', type=valid_pdf_extension,
    help='PDF file to be process')
  parser.add_argument('-j', '--jobs', metavar='N', default=2**32, 
    help='Allow N jobs at once; as many jobs as cpus with no arg.', type=int)
  parser.add_argument('--two-sided', action='store_true', 
    help='If set, will group pages for consistent two-sided printing')
  return parser.parse_args()

def valid_pdf_extension(name):
  if not name.endswith('.pdf'):
    msg = 'Unknown file extension: {0}'.format(name)
    raise argparse.ArgumentTypeError(msg)
  return name

if __name__ == '__main__':
  starttime = time.time()
  args = parse_args()
  basename = os.path.splitext(os.path.basename(args.pdf))[0]
  ## TODO: Use threads to speed-up this part
  original_pdf = PdfFileReader(open(args.pdf, 'rb'))
  min_pages_per_job = 10
  jobs = np.clip(args.jobs, 1, multiprocessing.cpu_count())
  num_pages = original_pdf.getNumPages()
  pages_per_job = max(num_pages/jobs, min_pages_per_job)
  pages_per_job = min(pages_per_job, num_pages)
  jobs = num_pages / pages_per_job
  num_digits = int(np.log10(jobs)) + 1
  ##
  # Extract color information
  infofile = basename + '.txt'
  gsargs  = [os.path.basename(sys.argv[0])]
  gsargs += ['-q', '-dBATCH', '-dNOPAUSE', '-sDEVICE=inkcov', '-dNOGC']
  gsargs += ['-o', infofile]
  gsargs += ['-f', args.pdf]
  ghostscript.Ghostscript(*gsargs)
  # Extract the color information for each page
  # Shape will be rows=num_pages, cols=4 (CMYK)
  pages = []
  num_black_pages = 0
  num_color_pages = 0
  num_white_pages = 0
  with open(os.path.expanduser(infofile), 'rb') as f:
    for i,line in enumerate(f):
      line = line.replace('  ', ' ')
      fields = line.split()
      if not len(fields) == 6:
        continue
      cmyk = map(float, fields[:4])
      number = i+1
      page = PageColorInfo(cmyk, number)
      pages.append(page)
      if page.is_color_page():
        num_color_pages += 1
      elif page.is_black_page():
        num_black_pages += 1
      else:
        num_white_pages += 1
  # Group pages in two: color and b&w
  color_pages = []
  bw_pages = []
  for number in range(1, len(pages), 2):
    odd_page = pages[number-1]
    even_page = pages[number]
    if args.two_sided:
      if odd_page.is_color_page() or even_page.is_color_page():
        color_pages.append(odd_page.get_number())
        color_pages.append(even_page.get_number())
      else:
        bw_pages.append(odd_page.get_number())
        bw_pages.append(even_page.get_number())
    else:
      if odd_page.is_color_page():
        color_pages.append(odd_page.get_number())
      else:
        bw_pages.append(odd_page.get_number())
      if even_page.is_color_page():
        color_pages.append(even_page.get_number())
      else:
        bw_pages.append(even_page.get_number())
  # Generate the two pdfs
  color_pdf = extract_pdf_pages(original_pdf, color_pages)
  with open(basename+'_color.pdf', 'wb') as f:
    color_pdf.write(f)
  bw_pdf = extract_pdf_pages(original_pdf, bw_pages)
  with open(basename+'_bw.pdf', 'wb') as f:
    bw_pdf.write(f)
  # Report
  duration = time.time() - starttime
  print '---'
  print 'Took {0:.3f} seconds'.format(duration)
