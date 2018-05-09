#!/bin/env python

import os
import sys
import argparse
import subprocess
from flask import Flask
from config import AWSConfig

app = Flask(__name__)

app.config.from_object(AWSConfig)

POSTGRES_DB = app.config.get('POSTGRES_DB')
POSTGRES_USER = app.config.get('POSTGRES_DB')
DB_URI = app.config.get('DB_URI')

parser = argparse.ArgumentParser(description='Input File')
parser.add_argument("-f", dest="filename", required=True,
                    help="input file to be parsed", metavar="FILE")

args = parser.parse_args()

if not os.path.exists(args.filename):
    print("Invalid file: exiting.")
    sys.exit(-1)


def setup_postgres():
    ret = subprocess.run(['which', 'psql'])
    if ret.returncode != 0:
        print("Postgres is either not installed or not in your path.  Exiting")
        sys.exit(-1)
    try:
        subprocess.run(['createdb', POSTGRES_DB])
        subprocess.run(['createuser', POSTGRES_USER])
    except subprocess.CalledProcessError as ex:
        print("Caught error creating postgres db and user: {}".format(ex))
        sys.exit(-1)
    try:
        subprocess.run(['python', 'create_db.py', '-f', args.filename])
    except subprocess.CalledProcessError as ex:
        print("Print failed loading pg db: {}".format(ex))
        sys.exit(-1)


def setup_redis():
    ret = subprocess.run(['which', 'redis-cli'])
    if ret.returncode != 0:
        print("Redis is either not installed or not in your path.  Exiting")
        sys.exit(-1)
    try:
        subprocess.run(['python', 'load_redis.py'])
    except subprocess.CalledProcessError as ex:
        print("Failed loading concepts into redis: {}".format(ex))
        sys.exit(-1)


def setup_es():
    ret = subprocess.run(['which', 'elasticsearch'])
    if ret.returncode != 0:
        print("Elasticsearch in either not installed or not in your path. Exiting")
        sys.exit(-1)
    try:
        subprocess.run(['python', 'load_es.py'])
    except subprocess.CalledProcessError as ex:
        print("Failed to load terms into elasticsearch: {}".format(ex))
        sys.exit(-1)

if __name__ == '__main__':
    setup_postgres()
    #setup_redis()
    #setup_es()
    print("Congrats!  Postgres database, redis database and Elasticsearch are ready to use")
