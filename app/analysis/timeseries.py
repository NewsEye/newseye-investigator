import assessment
from collections import defaultdict

# timeseries is a dictionary where keys are dates
# assume keys could be sorted by built-in sort() function

def ts_to_dist(ts):
    # converts timeseries to distribution
    return assessment.Distribution([ts[k] for k in sorted(ts)])

def ts_entropy(ts):
    return dist.entropy(ts_to_dict(ts))

def find_the_most_interesting(corpus, group, item="lemma", granularity="month", min_count = 10):
        #TODO: entropy-based comparison
        pass
        
def sum_up(timeseries):
    sum_ts = defaultdict(int)
    for ts in timeseries.values():
        for date, count in ts.items():
            sum_ts[date] += count
    return sum_ts

def compare_word_to_group(corpus, word, group, item="lemma", granularity="month", min_count = 10):           
    # output of this function is a timeseries, where key is a date
    # and value is a funciton that takes as an input word and group distributions
    # this means that an output might be sent to timeseries
    # processing functions to find steps
    word_list = set(group + [word])
    ts, ts_ipm = corpus.timeseries(item=item, granularity=granularity, min_count = min_count, word_list=word_list)
    total = corpus._timeseries[item][granularity]['total']

    try:
        word_ts = ts_ipm[word]
    except KeyError:
        raise KeyError("No information for word '%s'" %word)

    group_ts = sum_up ({w:ts_ipm[w] for w in group})

    # insert zeros for dates when these words are not mentioned
    assessment.align_dicts_from_to(total, word_ts)
    assessment.align_dicts_from_to(total, group_ts, assessment.EPSILON)
    
    return assessment.weighted_frequency_ratio(word_ts, group_ts, weights=total)
    

def find_group_kl(corpus, group, item="lemma", granularity="month", min_count = 10):
    ts, ts_ipm = corpus.timeseries(item=item, granularity=granularity, min_count = min_count, word_list=group)
    group_ts_ipm = corpus.sum_up_timeseries({w:ts_ipm[w] for w in group})        
    total = corpus._timeseries[item][granularity]['total']

    assessment.align_dicts_from_to(total, group_ts_ipm)
    group_dist = ts_to_dist(group_ts_ipm)

    for w in ts_ipm: align_dicts_from_to(total, ts_ipm[w]) 
    return {w:assessment.kl_divergence(ts_to_dist(ts_ipm[w]), group_dist) for w in ts_ipm}


def find_group_outlier(corpus, group, item="lemma", granularity="month", min_count = 10, weights = None):
    kl = (find_group_kl(corpus, group, item="lemma", granularity="month", min_count = 10))
    if weights:
        kl = {w:kl[w]*weights[w] for w in kl}
    return assessment.find_large_numbers(kl)






