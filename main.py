import json
import subprocess
import time
import traceback
from datetime import datetime, timedelta
from os.path import isfile
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


def get_empty_query(times):
    return [
        {
            'start-time': time,
            'end-time': times[i+1],
            'keywords': set()
        }
        for i, time in enumerate(times[:-1])
    ]


def get_now_keywords(query):
    now_keywords = set()
    for window in query:
        if window['start-time'] <= now():
            if window['end-time'] >= now():
                now_keywords |= window['keywords']
    return now_keywords


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


def iterate(name, sleep, stream_process, search_processes, log):
    with open(name + '.json') as query_file:
        query = convert_from_json(json.load(query_file))

    now_keywords = get_now_keywords(query)
    if now_keywords != stream_process['keywords']:
        log = stream(now_keywords, name, stream_process, log)

    query, log = get_standardized_queries(query, log)
    for query_window, log_window in zip(query, log):
        if len(query_window['keywords']) > 0:
            search_processes = search(
                query_window, log_window['keywords'], name, search_processes
            )
            log_window['keywords'] |= query_window['keywords']

    time.sleep(sleep)
    return search_processes, log


def kill_stream(stream_process, log):
    stream_process['end-time'] = now()
    if len(stream_process['keywords']) > 0:
        print('Killing old stream...')
        stream_process['process'].send_signal(SIGINT)
    else:
        stream_process['start-time'] = stream_process['end-time']
    del stream_process['process']
    del stream_process['number']
    return log + [stream_process]


def now():
    return str(datetime.utcnow()).replace(' ', 'T').split('.')[0]


def print_command(command):
    print(' '.join(command))


def read_log(name):
    if isfile(name + '-log.json'):
        with open(name + '-log.json') as f:
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


def search(window, negative_keywords, name, search_processes):
    search_processes += 1
    query = '(' + ') OR ('.join(window['keywords']) + ')'
    if len(negative_keywords) > 0:
        negative_query = '(' + ') OR ('.join(negative_keywords) + ')'
        query = '(' + query + ') AND NOT (' + negative_query + ')'
    query = '"' + query + '"'
    command = [
        'twarc2', 'search', '--hide-progress', '--archive',
        query, name + '-search-' + str(search_processes) + '.jsonl',
        '--start-time', window['start-time'], '--end-time', window['end-time']
    ]
    end_time = datetime.fromisoformat(window['end-time'])
    wait_until = end_time + timedelta(seconds=10)
    if wait_until > datetime.utcnow():
        time.sleep((wait_until - datetime.utcnow()).seconds + 1)
    print_command(command)
    subprocess.Popen(command)
    return search_processes


def stream(keywords, name, stream_process, log):
    old_stream_process = stream_process.copy()

    stream_process['keywords'] = keywords
    if len(keywords) > 0:
        stream_process['number'] += 1
        command = ['twarc2', 'stream-rules', 'delete-all']
        print_command(command)
        subprocess.run(command, stdout=subprocess.DEVNULL)
        for keyword in keywords:
            command = ['twarc2', 'stream-rules', 'add', '"' + keyword + '"']
            print_command(command)
            subprocess.run(command, stdout=subprocess.DEVNULL)
        command = [
            'twarc2', 'stream',
            name + '-stream-' + str(stream_process['number']) + '.jsonl',
        ]
        print_command(command)
        stream_process['process'] = subprocess.Popen(
            command, stderr=subprocess.DEVNULL
        )
        stream_process['start-time'] = now()
    else:
        stream_process['process'] = None
        stream_process['start-time'] = None
    log = kill_stream(old_stream_process, log)
    return log


def write_log(name, log, stream_processes, search_processes):
    with open(name + '-log.json', 'w') as f:
        json.dump({
            'stream_processes': stream_processes,
            'search_processes': search_processes,
            'log': [
                {
                    'start-time': window['start-time'],
                    'end-time': window['end-time'],
                    'keywords': list(window['keywords'])
                } for window in log
            ]
        }, f)


@click.command()
@click.option(
    '--sleep', default=60,
    help='''
        Seconds to sleep between each step of reading the configuration.
        Defaults to 60.
    '''
)
@click.argument('path')
def main(sleep, path):
    name = path.split('.json')[0]
    log, stream_process, search_processes = read_log(name)
    try:
        while True:
            search_processes, log = iterate(
                name, sleep, stream_process, search_processes, log
            )
    except KeyboardInterrupt:
        log = kill_stream(stream_process.copy(), log)
        write_log(name, log, stream_process['number'], search_processes)
    except Exception:
        traceback.print_exc()
        log = kill_stream(stream_process.copy(), log)
        write_log(name, log, stream_process['number'], search_processes)


if __name__ == '__main__':
    main()
