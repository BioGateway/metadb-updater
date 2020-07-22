import time
from pymongo import IndexModel, ASCENDING, TEXT, DESCENDING, MongoClient
from query_generators import *

indexes_prot_gene = [
        IndexModel([("prefLabel", ASCENDING)]),
        IndexModel([("synonyms", ASCENDING)]),
        IndexModel([("lcSynonyms", ASCENDING)]),
        IndexModel([("definition", TEXT)]),
        IndexModel([("lcLabel", ASCENDING)]),
        IndexModel([("refScore", DESCENDING)]),
        IndexModel([("fromScore", DESCENDING)]),
        IndexModel([("toScore", DESCENDING)]),
        IndexModel([("taxon", ASCENDING)])]

indexes_goall = [
        IndexModel([("prefLabel", ASCENDING)]),
        IndexModel([("synonyms", ASCENDING)]),
        IndexModel([("lcSynonyms", ASCENDING)]),
        IndexModel([("definition", ASCENDING)]),
        IndexModel([("lcLabel", TEXT)]),
        IndexModel([("refScore", DESCENDING)]),
        IndexModel([("fromScore", DESCENDING)]),
        IndexModel([("toScore", DESCENDING)])]


def drop_and_reset_database(dbName):
    db = MongoClient("mongodb://localhost:27017/")[dbName]

    db.command("dropDatabase")
    db.prot.create_indexes(indexes_prot_gene)
    db.gene.create_indexes(indexes_prot_gene)
    db.goall.create_indexes(indexes_goall)

def get_ref(db, collection):
    return db[collection.name]

def timestamp():
    return "[" + time.strftime("%H:%M:%S", time.localtime()) + "] "

def get_count(context, query):
    count_query = generate_count_query(query)
    url = generateUrl(context.baseUrl, count_query)
    data = urllib.request.urlopen(url)
    firstLine = True
    for line in data:
        if firstLine:
            firstLine = False
            continue
        count = int(line)
        return count


def update_labels(dataType, context, offset=None, batchSize=None, justCount=False):
    # startTime = time.time()
    # query = generate_name_label_query(dataType.graph, dataType.constraint)
    # if justCount:
    #     return get_count(context, query)
    #
    # mdb = MongoClient("mongodb://localhost:27017/")[context.dbName]
    # start_message = timestamp() + "Downloading label and description data for " + dataType.graph
    # if offset:
    #     start_message += " in " + str(batchSize) + " chunks. Offset: " + str(offset)
    # print(start_message)
    # limit = batchSize if offset else context.limit
    # url = generateUrl(context.baseUrl, query, limit, offset)
    # data = urllib.request.urlopen(url)
    #
    # firstLine = True
    # print(timestamp() + "Updating data for " + dataType.graph + "...")
    # counter = 0
    # for line in data:
    #     if firstLine:
    #         firstLine = False
    #         continue
    #     if counter % 10000 == 0:
    #         counterWithOffset = counter + offset
    #         print(timestamp() + " " + dataType.graph + " updated labels line " + str(counterWithOffset) + "...")
    #     update_labels_handler(mdb, dataType, line)
    #
    #     counter += 1
    #
    # durationTime = time.time() - startTime
    # print(timestamp() + "Updated " +
    #       str(counter) + " " + dataType.graph + " labels in " + time.strftime("%H:%M:%S.", time.gmtime(durationTime)))
    return updater_worker(dataType,
                   context, "labels",
                   generate_name_label_query(dataType.graph, dataType.constraint),
                   update_labels_handler,
                   offset,
                   batchSize,
                   justCount)

def updater_worker(dataType, context, name, query, handler_function, offset=None, batchSize=None, justCount=False):
    startTime = time.time()
    if justCount:
        return get_count(context, query)

    mdb = MongoClient("mongodb://localhost:27017/")[context.dbName]
    start_message = timestamp() + "Downloading " + name + " data for " + dataType.graph
    if offset:
        start_message += " in " + str(batchSize) + " chunks. Offset: " + str(offset)
    print(start_message)
    limit = batchSize if offset else context.limit
    url = generateUrl(context.baseUrl, query, limit, offset)
    data = urllib.request.urlopen(url)

    firstLine = True
    counter = 0
    for line in data:
        if firstLine:
            firstLine = False
            continue
        if counter % 10000 == 0:
            counterWithOffset = counter + offset
            print(timestamp() + dataType.graph + " updated " + name + " line " + str(counterWithOffset) + "...")
        handler_function(mdb, dataType, line)

        counter += 1

    durationTime = time.time() - startTime
    print(timestamp() + "Updated " +
          str(counter) + " " + dataType.graph + " " + name + " in " + time.strftime("%H:%M:%S.", time.gmtime(durationTime)))


def update_labels_handler(mdb, dataType, line):
    comps = line.decode("utf-8").replace("\"", "").replace("\n", "").split("\t")
    for collection in dataType.dbCollections:
        if collection.prefix:
            definition = collection.prefix + comps[2]
            update = {"$set": {"prefLabel": comps[1], "lcLabel": comps[1].lower(), "definition": definition}}
        else:
            update = {"$set": {"prefLabel": comps[1], "lcLabel": comps[1].lower(), "definition": comps[2]}}
        response = get_ref(mdb, collection).update_one({"_id": comps[0]}, update, upsert=True)

def update_synonyms(dataType, context, offset=None, batchSize=None, justCount=False):
    startTime = time.time()
    query = generate_field_query(dataType.graph, "skos:altLabel", dataType.constraint)
    if justCount:
        return get_count(context, query)

    mdb = MongoClient("mongodb://localhost:27017/")[context.dbName]
    startMessage = timestamp() + "Downloading synonym data for " + dataType.graph
    if offset:
        startMessage += " in " + str(batchSize) + " chunks. Offset: " + str(offset)
    print(startMessage)
    limit = batchSize if offset else context.limit
    url = generateUrl(context.baseUrl, query, limit, offset)
    data = urllib.request.urlopen(url)

    firstLine = True
    print(timestamp() + "Updating data for " + dataType.graph + "...")
    counter = 0
    for line in data:
        if firstLine:
            firstLine = False
            continue
        if counter % 10000 == 0:
            counterWithOffset = counter + offset
            print(timestamp() + " " + dataType.graph + " updated synonym line " + str(counterWithOffset) + "...")
        comps = line.decode("utf-8").replace("\"", "").replace("\n", "").split("\t")
        synonym = comps[1]
        update = {"$addToSet": {"synonyms": synonym, "lcSynonyms": synonym.lower()}}
        for dbCol in dataType.dbCollections:
            response = get_ref(mdb, dbCol).update_one({"_id": comps[0]}, update, upsert=True)

        counter += 1

    durationTime = time.time() - startTime
    print(timestamp() + "Updated " + str(counter) + " " + dataType.graph + " synonyms in " +
          time.strftime("%H:%M:%S.", time.gmtime(durationTime)))

def update_scores(dataType, context):
    startTime = time.time()
    mdb = MongoClient("mongodb://localhost:27017/")[context.dbName]

    print(timestamp() + "Downloading scores for " + dataType.graph + "...")
    query = generate_scores_query(dataType.graph, dataType.constraint)
    data = urllib.request.urlopen(generateUrl(context.baseUrl, query, context.limit))

    firstLine = True
    print(timestamp() + "Updating score data for " + dataType.graph + "...")
    counter = 0
    for line in data:
        if firstLine:
            firstLine = False
            continue
        if counter % 10000 == 0:
            print(timestamp() + " " + dataType.graph + " updated score line " + str(counter) + "...")
        comps = line.decode("utf-8").replace("\"", "").replace("\n", "").split("\t")
        fromScore = int(comps[1])
        toScore = int(comps[2])
        refScore = fromScore + toScore
        update = {"$set": {"refScore": refScore, "toScore": toScore, "fromScore": fromScore}}
        for dbCol in dataType.dbCollections:
            response = get_ref(mdb, dbCol).update_one({"_id": comps[0]}, update, upsert=True)

        counter += 1
    durationTime = time.time() - startTime
    print(timestamp() + "Updated " + dataType.graph + " scores in " + time.strftime("%H:%M:%S.",
                                                                                    time.gmtime(durationTime)))


def update_taxon(dataType, context):
    startTime = time.time()
    mdb = MongoClient("mongodb://localhost:27017/")[context.dbName]

    print(timestamp() + "Downloading taxa data for " + dataType.graph + "...")
    query = generate_field_query(dataType.graph, "<http://purl.obolibrary.org/obo/BFO_0000052>",
                                 dataType.constraint)
    data = urllib.request.urlopen(generateUrl(context.baseUrl, query, context.limit))

    firstLine = True
    print(timestamp() + "Updating taxon data for " + dataType.graph + "...")
    counter = 0
    for line in data:
        if firstLine:
            firstLine = False
            continue
        if counter % 10000 == 0:
            print(timestamp() + " " + dataType.graph + " updated taxon line " + str(counter) + "...")

        comps = line.decode("utf-8").replace("\"", "").replace("\n", "").split("\t")
        taxon = comps[1]
        update = {"$set": {"taxon": taxon}}
        for dbCol in dataType.dbCollections:
            response = get_ref(mdb, dbCol).update_one({"_id": comps[0]}, update, upsert=True)

        counter += 1
    durationTime = time.time() - startTime
    print(
        timestamp() + "Updated " + dataType.graph + " taxa in " + time.strftime("%H:%M:%S.", time.gmtime(durationTime)))


def update_instances(dataType, context):
    startTime = time.time()
    mdb = MongoClient("mongodb://localhost:27017/")[context.dbName]

    print(timestamp() + "Downloading instance data for " + dataType.graph + "...")
    query = generate_field_query(dataType.graph, "<http://schema.org/evidenceOrigin>",
                                 dataType.constraint)
    data = urllib.request.urlopen(generateUrl(context.baseUrl, query, context.limit))

    firstLine = True
    print(timestamp() + "Updating instance data for " + dataType.graph + "...")
    counter = 0
    for line in data:
        if firstLine:
            firstLine = False
            continue
        if counter % 10000 == 0:
            print(timestamp() + " " + dataType.graph + " updated instance data line " + str(counter) + "...")

        comps = line.decode("utf-8").replace("\"", "").replace("\n", "").split("\t")
        instance = comps[1]
        update = {"$addToSet": {"instances": instance}}
        for dbCol in dataType.dbCollections:
            response = get_ref(mdb, dbCol).update_one({"_id": comps[0]}, update, upsert=True)

        counter += 1
    durationTime = time.time() - startTime
    print(timestamp() + "Updated " + dataType.graph + " instances in " + time.strftime("%H:%M:%S.",
                                                                                       time.gmtime(durationTime)))


def update_annotationScore(dataType, context):
    startTime = time.time()
    mdb = MongoClient("mongodb://localhost:27017/")[context.dbName]

    print(timestamp() + "Downloading annotation scores for " + dataType.graph + "...")
    query = generate_field_query(dataType.graph, "<http://schema.org/evidenceLevel>",
                                 dataType.constraint)
    data = urllib.request.urlopen(generateUrl(context.baseUrl, query, context.limit))

    firstLine = True
    print(timestamp() + "Updating annotation scores for " + dataType.graph + "...")
    counter = 0
    for line in data:
        if firstLine:
            firstLine = False
            continue
        if counter % 10000 == 0:
            print(timestamp() + " " + dataType.graph + " updated annotation scores line " + str(counter) + "...")
        comps = line.decode("utf-8").replace("\"", "").replace("\n", "").split("\t")
        score = int(comps[1])
        update = {"$set": {"annotationScore": score}}
        for dbCol in dataType.dbCollections:
            response = get_ref(mdb, dbCol).update_one({"_id": comps[0]}, update, upsert=True)

        counter += 1
    durationTime = time.time() - startTime
    print(timestamp() + "Updated " + dataType.graph + " annotationScores in " + time.strftime("%H:%M:%S.", time.gmtime(
        durationTime)))
