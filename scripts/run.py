#!/usr/bin/python2.7

import collections
import getopt
import itertools
import json
import logging
import os
import signal
import subprocess
import sys
import time

# Constants --------------------------------------------------------------------

EXIT_SUCCESS = 0
EXIT_FAILURE = 1

COMPILER_ERROR     = 1
TIMELIMIT_EXCEEDED = 2
EXECUTION_ERROR    = 3
WRONG_ANSWER       = 4
WRONG_FORMATTING   = 5
PROGRAM_SUCCESS    = 6

# Globals ----------------------------------------------------------------------

Logger = logging.getLogger()

# Functions --------------------------------------------------------------------

def usage(exit_code=0):
    print >>sys.stderr, '''Usage: run [-d SANDBOX] [-t SECONDS -v] source input output

Options:

    -t SECONDS  Timeout duration before killing command (default is 30 seconds)
    -v          Display verbose debugging output
'''
    sys.exit(exit_code)

# Languages --------------------------------------------------------------------

LanguageFields = 'name compile execute extensions'.split()
Language       = collections.namedtuple('Language', LanguageFields)

LANGUAGES = (
    Language('Bash',
        '',
        'bash {source}',
        ('.sh',)
    ),
    Language('C',
        'gcc -std=gnu99 -o {executable} {source} -lm',
        './{executable}',
        ('.c',)
    ),
    Language('C++',
        'g++ -std=gnu++11 -o {executable} {source} -lm',
        './{executable}',
        ('.cc', '.cpp')
    ),
    Language('Go',
        'go build {source}',
        'go run {source}',
        ('.go',)
    ),
    Language('Java',
        'javac {source}',
        'java -cp . {executable}',
        ('.java',)
    ),
    Language('JavaScript',
        '',
        'nodejs {source}'
        , ('.js',)
    ),
    Language('Perl',
        '',
        'perl {source}'
        , ('.pl',)
    ),
    Language('Python',
        '',
        'python2.7 {source}',
        ('.py',)
    ),
    Language('Python 3',
        '',
        'python3.5 {source}',
        ('.py3',)
    ),
    Language('Ruby',
        '',
        'ruby {source}',
        ('.rb',)
    ),
    Language('Swift',
        '/opt/swift-3.1.1/bin/swiftc {source}',
        './{executable}',
        ('.swift',)
    ),
)

def get_language_from_source(source, language_name=None):
    extension = os.path.splitext(source)[-1]

    for language in LANGUAGES:
        matches_extension = extension in language.extensions
        matches_language  = language_name and language_name.lower() == language.name.lower()

        if matches_extension or matches_language:
            return language

    raise NotImplementedError

# Command ----------------------------------------------------------------------

def return_result(language, result, status=EXIT_FAILURE, score=COMPILER_ERROR):
    json.dump({'result': result, 'score': score}, sys.stdout)
    sys.exit(status)

def run(argv):
    timeout = 30

    try:
        options, arguments = getopt.getopt(argv[1:], "t:v")
    except getopt.GetoptError as e:
        Logger.error(e)

    for option, value in options:
        if option == '-v':
            Logger.setLevel(logging.DEBUG)
        elif option == '-t':
            timeout = int(value)
        else:
            usage(1)

    if not arguments:
        usage(1)

    source      = arguments[0]
    input       = arguments[1]
    output      = arguments[2]
    executable  = os.path.splitext(os.path.basename(source))[0]

    try:
        language = get_language_from_source(source)
    except NotImplementedError:
        message  = 'Unable to determine language for {}'.format(source)
        return_result('Unknwon', message, EXIT_FAILURE, COMPILER_ERROR)

    # Compile
    Logger.debug('Compiling {}...'.format(source))
    stdout  = open('stdout', 'w')
    command = language.compile.format(source=source, executable=executable)
    try:
        subprocess.check_call(command, shell=True, stdout=stdout, stderr=stdout)
    except subprocess.CalledProcessError:
        return_result(language.name, 'Compilation Error', EXIT_FAILURE, COMPILER_ERROR)

    # Execute
    Logger.debug('Executing {}...'.format(executable))
    command    = language.execute.format(source=source, executable=executable)
    stdout     = open('stdout', 'a')
    stdin      = open(input)
    start_time = time.time()
    toolong    = False

    try:
        process = subprocess.Popen(command.split(), stdin=stdin, stdout=stdout, stderr=open(os.devnull, 'w'), preexec_fn=os.setsid)
    except OSError:
        return_result(language.name, 'Execution Error', EXIT_FAILURE, EXECUTION_ERROR)

    try:
        while process.poll() is None:
            if time.time() - start_time >= timeout:
                toolong = True
                break
            time.sleep(0.25)
    finally:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except OSError:
            pass

    if toolong:
        return_result(language.name, 'Time Limit Exceeded', EXIT_FAILURE, TIMELIMIT_EXCEEDED)

    if process.returncode != 0:
        return_result(language.name, 'Execution Error', process.returncode, EXECUTION_ERROR)

    has_format_error = False
    for line0, line1 in itertools.izip_longest(open('stdout'), open(output)):
        if line0 is None or line1 is None:
            return_result(language.name, 'Wrong Answer', EXIT_FAILURE, WRONG_ANSWER)

        if line0 != line1:
            line0 = ''.join(line0.strip().split()).lower()
            line1 = ''.join(line1.strip().split()).lower()
            if line0 == line1:
                has_format_error = True
            else:
                return_result(language.name, 'Wrong Answer', EXIT_FAILURE, WRONG_ANSWER)

    if has_format_error:
        return_result(language.name, 'Output Format Error', EXIT_FAILURE, WRONG_FORMATTING)
    else:
        return_result(language.name, 'Success', EXIT_SUCCESS, PROGRAM_SUCCESS)

# Main Execution --------------------------------------------------------------

if __name__ == '__main__':
    # Set logging level
    logging.basicConfig(
        level   = logging.INFO,
        format  = '[%(asctime)s] %(message)s',
        datefmt = '%Y-%m-%d %H:%M:%S',
    )

    # Run command
    run(sys.argv)

# vim: set sts=4 sw=4 ts=8 expandtab ft=python:
