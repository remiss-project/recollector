import json
import subprocess
import time
import traceback
from datetime import datetime, timedelta
from os.path import isfile, isdir
from signal import SIGINT

import click


def add_seconds(time):
    return str(datetime.fromisoformat(time)).replace(' ', 'T').split('.')[0]


def convert_from_json(query):
    return [
        {
            'start-time': add_seconds(window['start-time']),
            'end-time': add_seconds(window['end-time']),
            'keywords': set(window['keywords'])
        } for window in query
    ]


def finish(log, stream_process, search_processes):
    stream_process['end-time'] = now()
    if stream_process['start-time'] is None:
        stream_process['start-time'] = stream_process['end-time']
    print('\n' + now() + ' Killing old stream...')
    stream_process['process'].send_signal(SIGINT)
    with open('log.json', 'w') as f:
        json.dump({
            'stream_processes': stream_process['number'],
            'search_processes': search_processes,
            'log': [
                {
                    'start-time': window['start-time'],
                    'end-time': window['end-time'],
                    'keywords': list(window['keywords'])
                } for window in log + [stream_process]
            ]
        }, f)


def get_empty_query(times):
    return [
        {
            'start-time': time,
            'end-time': times[i+1],
            'keywords': set()
        }
        for i, time in enumerate(times[:-1])
    ]


def get_past_times(query):
    start_times = [window['start-time'] for window in query]
    end_times = [window['end-time'] for window in query]
    times = start_times + end_times
    past_times = [time for time in times if time <= now()]
    return set(past_times)


def get_standardized_queries(query, log):
    times = get_past_times(query)
    times |= get_past_times(log)
    times = sorted(list(times))

    standard_log = get_empty_query(times)
    for window in log:
        for standard_window in standard_log:
            if is_inside(standard_window, window):
                standard_window['keywords'] |= window['keywords']
    standard_query = get_empty_query(times)
    for window in query:
        for standard_window, log_window in zip(standard_query, standard_log):
            if is_inside(standard_window, window):
                standard_window['keywords'] |= {
                    k for k in window['keywords']
                    if k not in log_window['keywords']
                }
    return standard_query, standard_log


def is_inside(inner_window, outer_window):
    if inner_window['start-time'] < outer_window['start-time']:
        return False
    if inner_window['end-time'] > outer_window['end-time']:
        return False
    return True


def iterate(infile, outfile, stream_process, search_processes, log):
    with open(infile) as query_file:
        query = convert_from_json(json.load(query_file))

    now_keywords = {
        keyword for window in query for keyword in window['keywords']
        if window['start-time'] <= now() and window['end-time'] >= now()
    }
    if now_keywords != stream_process['keywords']:
        log = stream(now_keywords, stream_process, log)

    query, log = get_standardized_queries(query, log)
    for query_window, log_window in zip(query, log):
        if len(query_window['keywords']) > 0:
            search_processes = search(
                query_window, log_window['keywords'], outfile, search_processes
            )
            log_window['keywords'] |= query_window['keywords']

    return search_processes, log


def now():
    return str(datetime.utcnow()).replace(' ', 'T').split('.')[0]


def read_log():
    if isfile('log.json'):
        with open('log.json') as f:
            log = json.load(f)
    else:
        log = {
            'stream_processes': 0,
            'search_processes': 0,
            'log': []
        }
    stream_process = {
        'keywords': set(),
        'start-time': None,
        'number': log['stream_processes'],
        'process': None
    }
    search_processes = log['search_processes']
    log = convert_from_json(log['log'])
    return log, stream_process, search_processes


def run(command, outfile, time=False):
    if time:
        print(now(), end=' ')
    print(' '.join(command))
    with open(outfile, 'a') as f:
        process = subprocess.Popen(command, stdout=f, stderr=f)
    return process


def search(window, negative_keywords, outfile, search_processes):
    search_processes += 1
    query = ' OR '.join(window['keywords'])
    if len(negative_keywords) > 0:
        negative_query = ' OR '.join(negative_keywords)
        query = '(' + query + ') -(' + negative_query + ')'
    query = '"' + query + '"'
    command = [
        'twarc2', 'search', '--archive',
        '--start-time', window['start-time'], '--end-time', window['end-time'],
        query, outfile + 'search-' + str(search_processes) + '.jsonl'
    ]
    end_time = datetime.fromisoformat(window['end-time'])
    wait_until = end_time + timedelta(seconds=10)
    if wait_until > datetime.utcnow():
        time.sleep((wait_until - datetime.utcnow()).seconds + 1)
    run(command, 'search-' + str(search_processes) + '.log')
    return search_processes


def stream(keywords, stream_process, log):
    old_stream_process = stream_process.copy()
    logfile = 'stream-' + str(stream_process['number']) + '.log'
    new_keywords = keywords - old_stream_process['keywords']
    old_keywords = old_stream_process['keywords'] - keywords

    for keyword in new_keywords:
        command = ['twarc2', 'stream-rules', 'add', '"' + keyword + '"']
        run(command, logfile, time=True)

    stream_process['start-time'] = now()
    stream_process['keywords'] = keywords

    old_stream_process['end-time'] = stream_process['start-time']
    if old_stream_process['start-time'] is None:
        old_stream_process['start-time'] = old_stream_process['end-time']

    for keyword in old_keywords:
        command = ['twarc2', 'stream-rules', 'delete', '"' + keyword + '"']
        run(command, logfile, time=True)

    return log + [old_stream_process]


@click.command()
@click.option(
    '--sleep', default=60,
    help='''
        Seconds to sleep between each step of reading the configuration.
        Defaults to 60.
    '''
)
@click.argument('infile')
@click.argument('outfile')
def main(sleep, infile, outfile):
    if '/' in outfile:
        out_directory = '/'.join(outfile.split('/')[:-1])
        assert isdir(out_directory)
    log, stream_process, search_processes = read_log()

    stream_process['number'] += 1
    logfile = 'stream-' + str(stream_process['number']) + '.log'
    run(['twarc2', 'stream-rules', 'delete-all'], logfile)

    try:
        command = [
            'twarc2', 'stream',
            outfile + 'stream-' + str(stream_process['number']) + '.jsonl',
        ]
        stream_process['process'] = run(command, logfile)
        while True:
            search_processes, log = iterate(
                infile, outfile, stream_process, search_processes, log
            )
            time.sleep(sleep)
    except KeyboardInterrupt:
        finish(log, stream_process, search_processes)
    except Exception:
        traceback.print_exc()
        finish(log, stream_process, search_processes)


if __name__ == '__main__':
    main()
