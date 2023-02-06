import json
import subprocess
import sys
import time
import traceback
from datetime import datetime, timedelta
from signal import SIGINT


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


def now():
    return str(datetime.utcnow()).replace(' ', 'T').split('.')[0]


def search(window, name, search_processes):
    search_processes += 1
    query = '"(' + ') OR ('.join(window['keywords']) + ')"'
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

    old_stream_process['end-time'] = now()
    if len(old_stream_process['keywords']) > 0:
        print('Killing old stream...')
        old_stream_process['process'].send_signal(SIGINT)
    else:
        old_stream_process['start-time'] = old_stream_process['end-time']
    del old_stream_process['process']
    del old_stream_process['number']
    log += [old_stream_process]


def print_command(command):
    print(' '.join(command))


def main(name, sleep, stream_process, search_processes, log):
    with open(name + '.json') as query_file:
        query = convert_from_json(json.load(query_file))

    now_keywords = get_now_keywords(query)
    if now_keywords != stream_process['keywords']:
        stream(now_keywords, name, stream_process, log)

    query, log = get_standardized_queries(query, log)
    for query_window, log_window in zip(query, log):
        if len(query_window['keywords']) > 0:
            search_processes = search(query_window, name, search_processes)
            log_window['keywords'] |= query_window['keywords']

    time.sleep(sleep)
    return search_processes, log


usage = """Usage: python3 main.py path [sleep]

path:  Path to json with configuracion.
sleep: Time sleep between each step of reading the configuration in seconds.
       Defaults to 60."""

if len(sys.argv) == 2:
    path = sys.argv[1]
    sleep = 60
elif len(sys.argv) == 3:
    path = sys.argv[1]
    sleep = int(sys.argv[2])
else:
    print(usage)
    exit(0)
name = path.split('.json')[0]
stream_process = {
    'keywords': set(),
    'start-time': None,
    'number': 0,
    'process': None
}
search_processes = 0
log = []

try:
    while (True):
        search_processes, log = main(
            name, sleep, stream_process, search_processes, log
        )
except KeyboardInterrupt:
    if stream_process['process'] is not None:
        print('Killing the stream...')
        stream_process['process'].send_signal(SIGINT)
except Exception:
    traceback.print_exc()
    if stream_process['process'] is not None:
        print('Killing the stream...')
        stream_process['process'].send_signal(SIGINT)
