#!  /usr/bin/env    python

# Utility script to create a NEW database.
# when loading data, DROP DATABASE thesaurus
# CREATE DATABASE thesaurus
# then run this script

from rdflib import ConjunctiveGraph, Literal
from rdflib_sqlalchemy import registerplugins
from flask import Flask
from config import DevelopmentConfig
from rdflib_sqlalchemy.store import SQLAlchemy

registerplugins()

app = Flask(__name__)
app.config.from_object(DevelopmentConfig)

DB_URI = app.config.get('DB_URI', None)
IDENTIFIER = app.config.get('IDENTIFIER', None)

uri = Literal(DB_URI)
store = SQLAlchemy(identifier=IDENTIFIER, configuration=uri)
graph = ConjunctiveGraph(store)
graph.parse(source='unbist-20180109.ttl', format='text/turtle', publicID=IDENTIFIER)
graph.commit()
print("Created new database '{}'".format(app.config.get("POSTGRES_DB")))
