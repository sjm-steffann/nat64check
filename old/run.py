#!/usr/bin/env python3.5

import multiprocessing
import os
import random
import signal
import subprocess
import time
from io import TextIOWrapper
from typing import Tuple

start = None
stop = False
count = 0


# noinspection PyUnusedLocal
def handle_signal(*args, **kwargs):
    global stop
    stop = True
    print('Stopping')


def check_domain(domain: str) -> int:
    started = time.time()

    result = None
    for i in range(5):
        result = subprocess.run(
            ['wget',
             '--quiet',
             # '--recursive', '--level=1',
             '--output-document=/run/user/0/dummy-output.{}'.format(os.getpid()), '--delete-after',
             '--no-check-certificate',
             '--timeout=20', '--tries=1',
             '--inet6-only',
             'www.' + domain],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        if result.returncode != 4:
            break

        print("Retrying {domain}".format(domain=domain))
        time.sleep((random.random() * 25) + 5)

    return result.returncode, started


def create_callback(domain: str, output: TextIOWrapper):
    def callback(return_value: Tuple[int, float]):
        global start, count

        result, started = return_value

        count += 1
        now = time.time()
        delay = now - started
        total_delay = now - start
        average = count / total_delay

        print('Done: {domain} in {delay:.2f}s resulted in {code} ({count} done: avg {average:.2f}/s)'.format(
            domain=domain, delay=delay, code=result, count=count, average=average))
        output.write('{domain},{result}\n'.format(domain=domain, result=result))

        if count % 10 == 0:
            output.flush()

    return callback


def run():
    global start, stop, count

    signal.signal(signal.SIGINT, signal.SIG_IGN)
    start = time.time()

    with open('results.txt', 'w') as output:
        with multiprocessing.Pool(processes=24) as pool:
            signal.signal(signal.SIGINT, handler=handle_signal)

            for domain in open('domains.txt'):
                domain = domain.strip()
                pool.apply_async(check_domain, args=(domain,), callback=create_callback(domain, output))

                if stop:
                    pool.terminate()
                    break

            pool.close()
            pool.join()


if __name__ == '__main__':
    run()
