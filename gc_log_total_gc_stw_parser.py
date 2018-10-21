#!python

import sys
import re
import tempfile
import os
import dateutil.parser

class LogParser:
  heapG1GCPattern = '\s*\[Eden: ([0-9.]+)([BKMG])\(([0-9.]+)([BKMG])\)->[0-9.BKMG()]+ Survivors: ([0-9.]+)([BKMG])->([0-9.]+)([BKMG]) Heap: ([0-9.]+)([BKMG])\([0-9.BKMG]+\)->([0-9.]+)([BKMG])\([0-9.BKMG]+\)'
  parallelPattern = '\s*\[PSYoungGen: ([0-9.]+)([BKMG])->([0-9.]+)([BKMG])\([0-9.MKBG]+\)\] ([0-9.]+)([MKBG])->([0-9.]+)([MKBG])\([0-9.MKBG]+\),'
  parallelFullPattern = '\s*\[PSYoungGen: ([0-9.]+)([BKMG])->([0-9.]+)([BKMG])\([0-9.MKBG]+\)\] \[ParOldGen: [0-9.BKMG]+->[0-9.BKMG]+\([0-9.MKBG]+\)\] ([0-9.]+)([MKBG])->([0-9.]+)([MKBG])\([0-9.MKBG]+\),'
  heapCMSPattern = '.*\[ParNew: ([0-9.]+)([BKMG])->([0-9.]+)([BKMG])\([0-9.BKMG]+\), [.0-9]+ secs\] ([0-9.]+)([BKMG])->([0-9.]+)([BKMG])\([0-9.BKMG]+\).*'
  rootScanStartPattern = '[0-9T\-\:\.\+]* ([0-9.]*): \[GC concurrent-root-region-scan-start\]'
  rootScanMarkEndPattern = '[0-9T\-\:\.\+]* ([0-9.]*): \[GC concurrent-mark-end, .*'
  rootScanEndPattern = '[0-9T\-\:\.\+]* ([0-9.]*): \[GC concurrent-cleanup-end, .*'
  mixedStartPattern = '\s*([0-9.]*): \[G1Ergonomics \(Mixed GCs\) start mixed GCs, .*'
  mixedContinuePattern = '\s*([0-9.]*): \[G1Ergonomics \(Mixed GCs\) continue mixed GCs, .*'
  mixedEndPattern = '\s*([0-9.]*): \[G1Ergonomics \(Mixed GCs\) do not continue mixed GCs, .*'
  exhaustionPattern = '.*\(to-space exhausted\).*'
  humongousObjectPattern = '.*request concurrent cycle initiation, .*, allocation request: ([0-9]*) .*, source: concurrent humongous allocation]'
  occupancyThresholdPattern = '.*threshold: ([0-9]*) bytes .*, source: end of GC\]'
  reclaimablePattern = '.*reclaimable: ([0-9]*) bytes \(([0-9.]*) %\), threshold: ([0-9]*).00 %]'

  def __init__(self, input_file):
    self.input_file = input_file
    self.gc_alg_g1gc = False
    self.gc_alg_cms = False
    self.gc_alg_parallel = False
    self.full_gc = False
    self.gc = False
    self.total_pause_time = 0
    # self.last_minute = -1
    self.reset_pause_counts()


  def determine_gc_alg(self):
    with open(self.input_file) as f:
      for line in f:
        m = re.match('^CommandLine flags: .*', line, flags=0)
        if m:
          if re.match(".*-XX:\+UseG1GC.*", line, flags=0):
            self.gc_alg_g1gc = True
            return

          elif re.match(".*-XX:\+UseConcMarkSweepGC.*", line, flags=0):
            self.gc_alg_cms = True
            return
          elif re.match(".*-XX:\+UseParallelGC.*", line, flags=0):
            self.gc_alg_parallel = True
            return

        m = re.match(LogParser.heapG1GCPattern, line, flags=0)
        if m:
          self.gc_alg_g1gc = True
          return

        m = re.match(LogParser.heapCMSPattern, line, flags=0)
        if m:
          self.gc_alg_cms = True
          return

        m = re.match(LogParser.parallelPattern, line, flags=0)
        if m:
          self.gc_alg_parallel = True
          return

  def parse_log(self):
    with open(self.input_file) as f:
      for line in f:
        # This needs to be first
        self.line_has_gc(line)

        # This needs to be last
        if self.line_has_pause_time(line):
          if self.full_gc:
            self.full_gc = False
          elif self.gc:
            self.gc = False

  def line_has_pause_time(self, line):
    m = re.match("[0-9-]*T[0-9]+:([0-9]+):.* threads were stopped: ([0-9.]+) seconds", line, flags=0)
    if not m or not (self.gc or self.full_gc):
      return False

    # cur_minute = int(m.group(1))
    self.pause_time = float(m.group(2))
    self.increment_pause_counts(self.pause_time)

    # if cur_minute != self.last_minute:
    #   self.last_minute = cur_minute
    #   self.reset_pause_counts()

    return True

  def line_has_gc(self, line):
    m = re.match(LogParser.heapG1GCPattern, line, flags=0)
    if m:
      self.gc = True
      return

    m = re.match(LogParser.parallelPattern, line, flags=0)
    if m:
      self.gc = True
      return

    m = re.match(LogParser.parallelFullPattern, line, flags=0)
    if m:
      self.full_gc = True

    m = re.match(LogParser.heapCMSPattern, line, flags=0)
    if m:
      self.gc = True

    return

  def increment_pause_counts(self, pause_time):
    self.total_pause_time = self.total_pause_time + pause_time

  def reset_pause_counts(self):
    self.total_pause_time = 0

def main():
    logParser = LogParser(sys.argv[1])
    try:
      logParser.determine_gc_alg()
      # print("gc alg: parallel=%s, g1gc=%s, cms=%s" % (logParser.gc_alg_parallel, logParser.gc_alg_g1gc, logParser.gc_alg_cms))
      logParser.parse_log()
      print("TOTAL GC STW TIME {}".format(logParser.total_pause_time))
    finally:
      pass


if __name__ == '__main__':
    main()
