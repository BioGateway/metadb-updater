#!/usr/bin/env python3
import argparse
import logging
import multiprocessing as mp
from dataclasses import dataclass

from updaters import *

format = "%(asctime)s: %(message)s"
logging.basicConfig(format=format, level=logging.INFO, datefmt="%H:%M:%S")

@dataclass
class DatabaseCollection:
    name: str
    prefix: str = ""


@dataclass
class DataType:
    graph: str
    dbCollections: [DatabaseCollection]
    constraint: str
    labels: bool
    scores: bool
    taxon: bool = False
    instances: bool = False
    annotationScores: bool = False

@dataclass
class UpdateContext:
    baseUrl: str
    dbName: str
    wipeData: bool
    batch_size: int
    parallel: bool

def timestamp():
    return "[" + time.strftime("%H:%M:%S", time.localtime()) + "] "

if __name__ == '__main__':
    startTime = time.time()
    mp.set_start_method('spawn')
    parser = argparse.ArgumentParser(
        description='Update the BioGateway Metadata Cache with new data from the SPARQL endpoint.')
    parser.add_argument('hostname', metavar='hostname', type=str,
                        help='The hostname of the BioGateway SPARQL endpoint to be loaded from.')
    parser.add_argument('port', metavar='port', type=str,
                        help='The port of the BioGateway SPARQL endpoint to be loaded from.')
    parser.add_argument('dbName', metavar='db-name', type=str, help='The MongoDB database to store the cached data')
    parser.add_argument('--datatype', type=str, help='Limit update to this data type.')
    parser.add_argument('--field', type=str, help='Limit update to this field type.')
    parser.add_argument('--batchsize', type=int, default=2000000, dest='batchsize', help='Batches the queries to N entries of each data type.')
    parser.add_argument('--drop', default=False, dest='drop', action='store_true', help='Drop all data from the database before updating.')
    parser.add_argument('--wipe', default=False, dest='wipe', action='store_true', help='Wipe all data from the collections being updated.')
    parser.add_argument('--parallel', default=False, dest='parallel', action='store_true', help='Run in parallel. This might cause instabilities.')

    args = parser.parse_args()

    baseUrl = args.hostname + ":" + args.port
    dbName = args.dbName
    wipeData = args.wipe
    query_batch_size = args.batchsize
    parallel = args.parallel
    dropDatabase = args.drop

    headerText = """
    %s          -------------------           METADATABASE UPDATER          -------------------
    %s                Updater tool for downloading and caching the BioGateway metadatabase.    
    %s                Parameters: <hostname:port> <db-name> (Optional)<datatype> (Optional)<fieldType>  
    %s                Connecting to endpoint on:        %s
    %s                Updating database:                %s
    %s                Parallel:                         %s
    %s          -------------------------------------------------------------------------------
    """ % (timestamp(), timestamp(), timestamp(), timestamp(), baseUrl, timestamp(), dbName, timestamp(), parallel, timestamp())

    print(headerText)

    print(timestamp() + 'Loading data into ' + dbName + ' using port ' + baseUrl + '...')

    dataTypes = [
        DataType("prot", [DatabaseCollection("prot")],
                 "?uri rdfs:subClassOf <http://semanticscience.org/resource/SIO_010043> .", True, True, True, True, True),
        DataType("gene", [DatabaseCollection("gene")],
                 "?uri rdfs:subClassOf <http://semanticscience.org/resource/SIO_010035> .", True, True, True, True),
        DataType("omim", [DatabaseCollection("omim")], "", True, True),
        DataType("go", [DatabaseCollection("gobp"), DatabaseCollection("goall", "Biological Process")],
                 generate_GO_namespace_constraint("biological_process"), True, True),
        DataType("go", [DatabaseCollection("gocc"), DatabaseCollection("goall", "Cellular Component")],
                 generate_GO_namespace_constraint("cellular_component"), True, True),
        DataType("go", [DatabaseCollection("gomf"), DatabaseCollection("goall", "Molecular Function")],
                 generate_GO_namespace_constraint("molecular_function"), True, True),
        DataType("prot2prot", [DatabaseCollection("prot2prot")], "", True, False, False, True),
        DataType("prot2onto", [DatabaseCollection("prot2onto")], "", True, False),
        DataType("tfac2gene", [DatabaseCollection("tfac2gene")], "", True, False)
    ]

    limitToDatatype = args.datatype
    limitToFieldType = args.field

    if limitToDatatype:
        dataTypes = list(filter(lambda x: x.graph == limitToDatatype, dataTypes))

    if limitToFieldType:
        for dataType in dataTypes:
            if limitToFieldType == "label":
                dataType.labels = True
                dataType.scores = False
                dataType.taxon = False
                dataType.instances = False
            if limitToFieldType == "scores":
                dataType.labels = False
                dataType.scores = True
                dataType.taxon = False
                dataType.instances = False
            if limitToFieldType == "taxon":
                dataType.labels = False
                dataType.scores = False
                dataType.taxon = True
                dataType.instances = False
            if limitToFieldType == "instances":
                dataType.labels = False
                dataType.scores = False
                dataType.taxon = False
                dataType.instances = True
            if limitToFieldType == "annotationScores":
                dataType.labels = False
                dataType.scores = False
                dataType.taxon = False
                dataType.instances = False
                dataType.annotationScores = True

    if dropDatabase:
        print("Dropping database " + dbName + "and rebuilding indexes.")
        drop_and_reset_database(dbName)
        print("Database " + dbName + " has been reset.")

    print(timestamp() + "Updating:")
    print(*dataTypes, sep="\n")

    context = UpdateContext(args.hostname + ":" + args.port, args.dbName, args.wipe, args.batchsize, args.parallel)


    for dataType in dataTypes:
        if wipeData:
            for collection in dataType.dbCollections:
                print("Wiping collection: " + collection.name)
                collection.reference.delete_many({})

    processes = []

    for dataType in dataTypes:
        if dataType.labels:
            if parallel:
                processes.extend(startBatches(dataType, "labels", update_labels, context))
                processes.extend(startBatches(dataType, "synonyms", update_synonyms, context))
            else:
                update_labels(dataType, context)
                update_synonyms(dataType, context)

        if dataType.scores:
            if parallel:
                processes.extend(startBatches(dataType, "scores", update_scores, context))

            else:
                update_scores(dataType, context)

        if dataType.taxon:
            if parallel:
                processes.extend(startBatches(dataType, "taxon", update_taxon, context))
            else:
                update_taxon(dataType, context)

        if dataType.instances:
            if parallel:
                processes.extend(startBatches(dataType, "instances", update_instances, context))
            else:
                update_instances(dataType, context)

        if dataType.annotationScores:
            if parallel:
                processes.extend(startBatches(dataType, "annotation score", update_annotationScore, context))
            else:
                update_annotationScore(dataType, context)

    # Start all processes:
    print(timestamp() + "Starting " + str(len(processes)) + " workers...")
    for process in processes:
        process.start()

    # Wait for all processes to complete:
    for process in processes:
        process.join()

    durationTime = time.time() - startTime
    print(timestamp() + "All updates completed in: " + time.strftime("%H:%M:%S.", time.gmtime(durationTime)))
