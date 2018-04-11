#!  /usr/bin/env    python

# Utility script to create a NEW database.
# when loading data, DROP DATABASE thesaurus
# CREATE DATABASE thesaurus
# then run this script

import argparse
from rdflib import ConjunctiveGraph, Literal
from rdflib_sqlalchemy import registerplugins
from flask import Flask
from config import DevelopmentConfig
from rdflib_sqlalchemy.store import SQLAlchemy
import os.path
import sys

registerplugins()

app = Flask(__name__)
app.config.from_object(DevelopmentConfig)


parser = argparse.ArgumentParser(description='Input File')
parser.add_argument("-f", dest="filename", required=True,
                    help="input file to be parsed", metavar="FILE")

args = parser.parse_args()

if not os.path.exists(args.filename):
    print("Invalid file: exiting.")
    sys.exit(-1)

DB_URI = app.config.get('DB_URI', None)
IDENTIFIER = app.config.get('IDENTIFIER', None)

uri = Literal(DB_URI)
store = SQLAlchemy(identifier=IDENTIFIER, configuration=uri)
graph = ConjunctiveGraph(store)
graph.parse(source=args.filename, format='text/turtle', publicID=IDENTIFIER)
graph.commit()
print("Created new database '{}'".format(app.config.get("POSTGRES_DB")))
