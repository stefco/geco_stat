"""
Tools for computing aggregated statistics over multiple frame files for
a given channel.
Stefan Countryman
"""

import sys
import os
import subprocess
import datetime
import numpy as np

"""
get the current time
"""
def now():
    return str(datetime.datetime.now())

# Get channel names.
ch = {
    'h_irigb': 'H1:CAL-PCALX_IRIGB_OUT_DQ',
    'h_dtone': 'H1:CAL-PCALY_FPGA_DTONE_IN1_DQ',
    'l_irigb': 'L1:CAL-PCALX_IRIGB_OUT_DQ',
    'l_dtone': 'L1:CAL-PCALY_FPGA_DTONE_IN1_DQ'
}

# Set the bitrate for a 16k channel.
kbps16 = 16384
sec_per_frame = 64

# the min and max values for irigb and dtone histograms
irigb_hist_min = -20000
irigb_hist_max = 44000
dtone_hist_min = -1000
dtone_hist_max = 1000
dtone_hist_close_min = -1
dtone_hist_close_max = 1
dtone_nbins = 100

"""
remove first n lines of a string
"""
def remove_lines(string, num_lines):
    i = 0
    n = 0
    l = len(string)
    while n < num_lines:
        i = string.find('\n', i+1)
        # if a newline isn't found, this means there are no new lines left.
        if i == -1:
            return ""
        # if the string ends on a newline, return empty string.
        elif i+1 == l:
            return ""
        n += 1
    return string[i+1:]

"""
Delete first 6 lines; all spaces; and the word 'Data:' which precedes the
numerical data.

(This replaces sed and tr in the original implementation with native python.)
"""
def remove_header_and_text(string):
    return remove_lines(string, 6).translate(None, 'Dat: ')

"""
Load channel from file path to array.

If a channel doesn't exist within the
frame file located at the specified path, this function will return None.
Otherwise, it returns an ndarray with one row for each second of data in the
frame file.
"""
def ndarray_from_file(channel, path, bitrate=kbps16):
    # make sure path exists
    if not os.path.exists(path):
        raise ValueError('Path does not exist: ' + path)

    # set up the processes for acquiring and processing the data
    dump = subprocess.Popen(["framecpp_dump_channel","--channel",channel,path], stdout=subprocess.PIPE)
    data_string = dump.communicate()[0]
    print now() + ' Timeseries retrieved, beginning processing.'

    # remove headers from the data
    formatted_data_string = remove_header_and_text(data_string)

    # if the string is empty, the channel didn't exist. return None.
    if formatted_data_string == '':
        return None

    # instantiate numpy array and return it; will have number of rows equal to
    # the number of seconds in a frame file and number of columns equal to the
    # bitrate of the channel.
    return np.fromstring(formatted_data_string, sep=',').reshape((sec_per_frame, bitrate))

"""
Take a histogram of the given data with the specified bin number and range of
values. Then, add that to the existing histogram array (which is assumed to have
the correct dimensions).

Returns: aggregate_histogram, bins

WARNING: will modify the value of aggregate_histogram.
"""
def histogram_array_accumulate(data, aggregate_histogram, min, max, nbins=256):
    # if the aggregate_array is None, just initialize a new array with the proper shape
    if aggregate_histogram == None:
        aggregate_histogram = np.zeros((nbins, data.shape[1]), dtype=np.int64)

    # create a histogram for the corresponding moment within each second
    if aggregate_histogram.shape != (nbins, data.shape[1]):
        raise ValueError('aggregate_histogram has the wrong shape!')

    # get the bin number by running once
    h = np.histogram(data[:,0], bins=nbins, range=(min,max))
    aggregate_histogram[:,0] += h[0]
    bins = h[1]
    for i in range(1, data.shape[1]):
        aggregate_histogram[:,i] += np.histogram(data[:,i], bins=nbins, range=(min,max))[0]

    return aggregate_histogram, bins

"""
load the specified channel from each frame file in the list of paths provided
and aggregate statistics on it FOR DTONE
"""
def run_avg_dtone(channel, frame_list_file, outfile_prefix, mean_val_file=None):

    # since this is for dtone, we do need a mean value file; mean value file is
    # assumed to only show mean value over one second.
    if mean_val_file == None:
        raise ValueError('Must provide mean value file for DuoTone.')
    else:
        mean = np.loadtxt(mean_val_file) * np.ones((sec_per_frame,1))

    # get list of paths to the frame files
    with open(frame_list_file, 'r') as f:
        frame_file_paths = f.read().splitlines()

    # initialize aggregate statistics with frame file located at first path
    i = 0                               # current path
    l = len(frame_file_paths)           # total number of paths

    # load first file
    print now() + ' Loading frame at first path into array...'
    data = ndarray_from_file(channel, frame_file_paths[i])

    # check if the frame file actually contained this channel
    if data == None:
        with open(outfile_prefix + '.skipped', 'a') as f:
            f.write(frame_file_paths[i] + '\n')

    # initialize statistics
    print now() + ' Done. Initializing aggregate statistics variables...'
    sum             = data.sum(0)
    sum_sq          = np.power(data, 2).sum(0)
    max             = np.max(data,0)
    min             = np.min(data,0)
    hist, bins      = histogram_array_accumulate(data, None, dtone_hist_min, dtone_hist_max, nbins=dtone_nbins)
    # for duotone, also keep 'zoomed in' histogram
    hist_c, bins_c  = histogram_array_accumulate(data, None, dtone_hist_close_min, dtone_hist_close_max, nbins=dtone_nbins)
    # for duotone, check whether this is significantly different from the mean
    if np.max(np.abs(data-mean)) > 10:
        print now() + ' Anomaly found in frame file ' + frame_file_paths[i]
        with open(outfile_prefix + '.anomaly', 'a') as f:
            f.write(frame_file_paths[i] + '\n')
    num             = data.shape[0]
    print now() + ' Done initializing.'
    i += 1

    # iterate through the rest of the files
    while i < l:
        # load file
        print now() + ' Loading frame ' + str(i+1) + ' of ' + str(l) + ' into array...'
        data = ndarray_from_file(channel, frame_file_paths[i])

        # continue to generate statistics
        print now() + ' Done. Aggregating statistics...'
        sum     += data.sum(0)
        sum_sq  += np.power(data, 2).sum(0)
        max     =  np.maximum(np.max(data,0), max)
        min     =  np.minimum(np.min(data,0), min)
        hist    =  histogram_array_accumulate(data, hist, dtone_hist_min, dtone_hist_max, nbins=dtone_nbins)[0]
        # for duotone, also keep 'zoomed in' histogram
        hist_c  =  histogram_array_accumulate(data, hist_c, dtone_hist_close_min, dtone_hist_close_max, nbins=dtone_nbins)[0]
        # for duotone, check whether this is significantly different from the mean
        if np.max(np.abs(data-mean)) > 10:
            print now() + ' Anomaly found in frame file ' + frame_file_paths[i]
            with open(outfile_prefix + '.anomaly', 'a') as f:
                f.write(frame_file_paths[i] + '\n')
        num     += data.shape[0]
        print now() + ' Done.'
        i += 1

    # save files
    sum.tofile(outfile_prefix + '.sum', sep='\n')
    sum_sq.tofile(outfile_prefix + '.sumsq', sep='\n')
    max.tofile(outfile_prefix + '.max', sep='\n')
    min.tofile(outfile_prefix + '.min', sep='\n')
    hist.tofile(outfile_prefix + '.hist', sep='\n')
    bins.tofile(outfile_prefix + '.hist.bins', sep='\n')
    hist_c.tofile(outfile_prefix + '.hist_close', sep='\n')
    bins_c.tofile(outfile_prefix + '.hist_close.bins', sep='\n')
    with open(outfile_prefix + '.num', 'w') as f: f.write(str(num))

"""
load the specified channel from each frame file in the list of paths provided
and aggregate statistics on it FOR IRIGB
"""
def run_avg_irigb(channel, frame_list_file, outfile_prefix, mean_val_file=None):
    # get list of paths to the frame files
    with open(frame_list_file, 'r') as f:
        frame_file_paths = f.read().splitlines()

    # initialize aggregate statistics with frame file located at first path
    i = 0                               # current path
    l = len(frame_file_paths)           # total number of paths

    # load first file
    print now() + ' Loading frame at first path into array...'
    data = ndarray_from_file(channel, frame_file_paths[i])

    # check if the frame file actually contained this channel
    if data == None:
        with open(outfile_prefix + '.skipped', 'a') as f:
            f.write(frame_file_paths[i] + '\n')

    # initialize statistics
    print now() + ' Done. Initializing aggregate statistics variables...'
    sum             = data.sum(0)
    sum_sq          = np.power(data, 2).sum(0)
    max             = np.max(data,0)
    min             = np.min(data,0)
    hist, bins      = histogram_array_accumulate(data, None, irigb_hist_min, irigb_hist_max)
    num             = data.shape[0]
    print now() + ' Done initializing.'
    i += 1

    # iterate through the rest of the files
    while i < l:
        # load file
        print now() + ' Loading frame ' + str(i+1) + ' of ' + str(l) + ' into array...'
        data = ndarray_from_file(channel, frame_file_paths[i])

        # continue to generate statistics
        print now() + ' Done. Aggregating statistics...'
        sum     += data.sum(0)
        sum_sq  += np.power(data, 2).sum(0)
        max     =  np.maximum(np.max(data,0), max)
        min     =  np.minimum(np.min(data,0), min)
        hist    =  histogram_array_accumulate(data, hist, irigb_hist_min, irigb_hist_max)[0]
        num     += data.shape[0]
        print now() + ' Done.'
        i += 1

    # save files
    sum.tofile(outfile_prefix + '.sum', sep='\n')
    sum_sq.tofile(outfile_prefix + '.sumsq', sep='\n')
    max.tofile(outfile_prefix + '.max', sep='\n')
    min.tofile(outfile_prefix + '.min', sep='\n')
    hist.tofile(outfile_prefix + '.hist', sep='\n')
    bins.tofile(outfile_prefix + '.hist.bins', sep='\n')
    with open(outfile_prefix + '.num', 'w') as f: f.write(str(num))

def __run_l_irigb(frame_list_file, outfile_prefix, mean_val_file=None):
    run_avg_irigb(ch['l_irigb'], frame_list_file, outfile_prefix)

def __run_h_irigb(frame_list_file, outfile_prefix, mean_val_file=None):
    run_avg_irigb(ch['h_irigb'], frame_list_file, outfile_prefix)

def __run_l_dtone(frame_list_file, outfile_prefix, mean_val_file=None):
    run_avg_dtone(ch['l_dtone'], frame_list_file, outfile_prefix, mean_val_file)

def __run_h_dtone(frame_list_file, outfile_prefix, mean_val_file=None):
    run_avg_dtone(ch['h_dtone'], frame_list_file, outfile_prefix, mean_val_file)

run = {
    'h_irigb': __run_h_irigb,
    'l_irigb': __run_l_irigb,
    'h_dtone': __run_h_dtone,
    'l_dtone': __run_l_dtone
}

"""
Take all text data outfiles with specified prefix (and that are finished, as
indicated by a donefile) and aggregate the statistical information they contain.

Usage: takes two arguments, the first of which is a prefix for the outfile
containing aggregate statistics, and the second of which is an array of
file prefixes for batches of statistics files.
"""
def aggregate_files_irigb(aggregate_prefix, infile_prefixes):
    print now() + ' Initializing, loading first batch of statistics from ' + infile_prefixes[0]
    # initialize
    agg_sum     = np.loadtxt(infile_prefixes[0] + '.sum')
    agg_sum_sq  = np.loadtxt(infile_prefixes[0] + '.sumsq')
    agg_max     = np.loadtxt(infile_prefixes[0] + '.max')
    agg_min     = np.loadtxt(infile_prefixes[0] + '.min')
    agg_num     = np.loadtxt(infile_prefixes[0] + '.num', dtype=int)
    agg_hist    = np.loadtxt(infile_prefixes[0] + '.hist').reshape((256, kbps16))
    hist_bins   = np.loadtxt(infile_prefixes[0] + '.hist.bins')

    # iterate through, loading stats from each frame file list
    for i in range(1,len(infile_prefixes)):
        print now() + 'Adding statistics batch ' + str(i) + ' from ' + infile_prefixes[i]
        sum     = np.loadtxt(infile_prefixes[i] + '.sum')
        sum_sq  = np.loadtxt(infile_prefixes[i] + '.sumsq')
        max     = np.loadtxt(infile_prefixes[i] + '.max')
        min     = np.loadtxt(infile_prefixes[i] + '.min')
        num     = np.loadtxt(infile_prefixes[i] + '.num', dtype=int)

        # add data to the aggregated statistics
        agg_sum     +=  sum
        agg_sum_sq  +=  sum_sq
        agg_max     =   np.maximum(agg_max, max)
        agg_min     =   np.minimum(agg_min, min)
        agg_num     += num

    # calculate mean and variance
    agg_mean        = agg_sum / agg_num
    agg_var         = agg_sum_sq / agg_num  -  np.square(agg_mean)

    # save the output to text files
    print now() + 'Done. Saving to text files with prefix ' + aggregate_prefix
    agg_sum.tofile(aggregate_prefix + '.sum.txt', sep="\n")
    agg_sum_sq.tofile(aggregate_prefix + '.sumsq.txt', sep="\n")
    agg_max.tofile(aggregate_prefix + '.max.txt', sep="\n")
    agg_min.tofile(aggregate_prefix + '.min.txt', sep="\n")
    agg_num.tofile(aggregate_prefix + '.num.txt', sep="\n")
    agg_hist.tofile(aggregate_prefix + '.hist.txt', sep="\n")
    hist_bins.tofile(aggregate_prefix + '.hist_bins.txt', sep="\n")
    agg_mean.tofile(aggregate_prefix + '.mean.txt', sep="\n")
    agg_var.tofile(aggregate_prefix + '.var.txt', sep="\n")
    print now() + '\nDONE.'

"""
Take all text data outfiles with specified prefix (and that are finished, as
indicated by a donefile) and aggregate the statistical information they contain.

Usage: takes two arguments, the first of which is a prefix for the outfile
containing aggregate statistics, and the second of which is an array of
file prefixes for batches of statistics files.
"""
def aggregate_files_dtone(aggregate_prefix, infile_prefixes):
    print now() + ' Initializing, loading first batch of statistics from ' + infile_prefixes[0]
    # initialize
    agg_sum     = np.loadtxt(infile_prefixes[0] + '.sum')
    agg_sum_sq  = np.loadtxt(infile_prefixes[0] + '.sumsq')
    agg_max     = np.loadtxt(infile_prefixes[0] + '.max')
    agg_min     = np.loadtxt(infile_prefixes[0] + '.min')
    agg_num     = np.loadtxt(infile_prefixes[0] + '.num', dtype=int)
    agg_hist    = np.loadtxt(infile_prefixes[0] + '.hist').reshape((dtone_nbins, kbps16))
    agg_hist_c  = np.loadtxt(infile_prefixes[0] + '.hist_close').reshape((dtone_nbins, kbps16))
    hist_bins   = np.loadtxt(infile_prefixes[0] + '.hist.bins')
    hist_c_bins = np.loadtxt(infile_prefixes[0] + '.hist_close.bins')

    # iterate through, loading stats from each frame file list
    for i in range(1,len(infile_prefixes)):
        print now() + 'Adding statistics batch ' + str(i) + ' from ' + infile_prefixes[i]
        sum     = np.loadtxt(infile_prefixes[i] + '.sum')
        sum_sq  = np.loadtxt(infile_prefixes[i] + '.sumsq')
        max     = np.loadtxt(infile_prefixes[i] + '.max')
        min     = np.loadtxt(infile_prefixes[i] + '.min')
        num     = np.loadtxt(infile_prefixes[i] + '.num', dtype=int)
        hist    = np.loadtxt(infile_prefixes[i] + '.hist').reshape((dtone_nbins, kbps16))
        hist_c  = np.loadtxt(infile_prefixes[i] + '.hist_close').reshape((dtone_nbins, kbps16))

        # add data to the aggregated statistics
        agg_sum     +=  sum
        agg_sum_sq  +=  sum_sq
        agg_max     =   np.maximum(agg_max, max)
        agg_min     =   np.minimum(agg_min, min)
        agg_num     += num
        agg_hist    += hist
        agg_hist_c  += hist_c

    # calculate mean and variance
    agg_mean        = agg_sum / agg_num
    agg_var         = agg_sum_sq / agg_num  -  np.square(agg_mean)

    # save the output to text files
    print now() + 'Done. Saving to text files with prefix ' + aggregate_prefix
    agg_sum.tofile(aggregate_prefix + '.sum.txt', sep="\n")
    agg_sum_sq.tofile(aggregate_prefix + '.sumsq.txt', sep="\n")
    agg_max.tofile(aggregate_prefix + '.max.txt', sep="\n")
    agg_min.tofile(aggregate_prefix + '.min.txt', sep="\n")
    agg_num.tofile(aggregate_prefix + '.num.txt', sep="\n")
    agg_hist.tofile(aggregate_prefix + '.hist.txt', sep="\n")
    agg_mean.tofile(aggregate_prefix + '.mean.txt', sep="\n")
    agg_var.tofile(aggregate_prefix + '.var.txt', sep="\n")
    agg_hist_c.tofile(aggregate_prefix + '.hist_close.txt', sep="\n")
    hist_bins.tofile(aggregate_prefix + '.hist_bins.txt', sep="\n")
    hist_c_bins.tofile(aggregate_prefix + '.hist_close_bins.txt', sep="\n")
    print now() + '\nDONE.'

aggregate = {
    'h_irigb': aggregate_files_irigb,
    'l_irigb': aggregate_files_irigb,
    'h_dtone': aggregate_files_dtone,
    'l_dtone': aggregate_files_dtone
}

